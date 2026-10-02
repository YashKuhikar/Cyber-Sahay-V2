from __future__ import annotations

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from ..logs.logger import logger
from ..memory.case_profile_v2 import CaseProfileV2, create_case_profile_v2, update_case_profile_v2
from ..memory.memory_manager import MemoryManager
from ..rag.multilingual import MultilingualProcessor
from .advisor_agent import AdvisorAgent
from .complaint_agent import ComplaintAgent
from .entity_extractor import TypedEntityExtractor
from .fir_agent import FIRAgent
from .fir_orchestrator import FIROrchestrator
from .fir_extractor import (
    FIRInformationExtractor,
    format_extracted_summary,
    format_confirmation_summary,
    FIELD_QUESTION_MAP,
    INCIDENT_REQUIREMENTS,
)
from .information_extraction_agent import InformationExtractionAgent
from .intent_agent import IntentAgent
from .response_formatter import ResponseFormatter
from .retrieval_agent import RetrievalAgent
from .safety_agent import SafetyAgent
from .state_machine import ConversationState, ConversationStateMachine
from .verifier_agent import VerifierAgent

GREETING_PATTERNS = {
    "hi", "hello", "hey", "namaste", "namaskar", "good morning",
    "good afternoon", "good evening", "hii", "heyy", "hello there",
    "greetings", "help",
}

GRATITUDE_PATTERNS = {
    "thank you", "thanks", "thank u", "thanks a lot", "thank you so much",
    "thx", "ok thanks", "okay thanks", "ok thank you", "okay thank you",
    "thank you for your help", "thanks for help", "thank you for the information",
    "got it thanks", "understood thanks", "appreciate it", "many thanks",
    "ok thank you so much", "okay thank you so much", "thank you sir",
    "thank you maam", "thanks sir",
}

CLOSING_PATTERNS = {
    "bye", "goodbye", "good bye", "ok bye", "see you", "take care",
    "exit", "quit",
}


def get_direct_conversational_reply(query: str) -> tuple[str, str, str] | None:
    cleaned = query.strip().lower().rstrip(".!?,:;~")
    if not cleaned:
        return None

    if cleaned in GRATITUDE_PATTERNS or cleaned.startswith("thank you") or cleaned.startswith("thanks"):
        return (
            "greeting",
            "greeting",
            "You're very welcome! Stay safe online. If you need any further legal guidance, precautions, or assistance in filing a complaint or FIR draft, feel free to ask anytime.",
        )

    if cleaned in GREETING_PATTERNS or cleaned.startswith("hello ") or cleaned.startswith("hi "):
        return (
            "greeting",
            "greeting",
            "Hello! I am CyberSahay, your AI assistant for Indian cyber safety, fraud containment, and cybercrime reporting. How can I assist you today?",
        )

    if cleaned in CLOSING_PATTERNS:
        return (
            "greeting",
            "greeting",
            "Goodbye and stay vigilant online! You can reach out to CyberSahay anytime whenever you need cybercrime assistance or guidance.",
        )

    return None


class CoordinatorAgent:
    """
    CyberSahay V2 Multi-Agent Orchestrator.
    Pipeline:
    User Message -> Safety Triage -> Typed Extraction -> Case Profile V2 Update ->
    Conversation State Machine -> Hybrid Retrieval V2 (Reranked) -> Grounded Generation ->
    Verifier Agent -> Victim-Friendly Response Formatter.
    """

    def __init__(self, memory: Optional[MemoryManager] = None):
        self.safety_agent = SafetyAgent()
        self.entity_extractor = TypedEntityExtractor()
        self.intent_agent = IntentAgent()
        self.retrieval_agent = RetrievalAgent()
        self.complaint_agent = ComplaintAgent()
        self.fir_agent = FIRAgent()
        self.fir_orchestrator = FIROrchestrator()
        self.advisor_agent = AdvisorAgent()
        self.information_extraction_agent = InformationExtractionAgent()
        self.verifier_agent = VerifierAgent()
        self.fir_extractor = FIRInformationExtractor()
        self.memory = memory if memory is not None else MemoryManager()

    def handle(self, session_id: str, query: str) -> Dict[str, Any]:
        start = time.time()
        self.memory.add_user_message(session_id, query)
        history = self.memory.get_history(session_id)

        # 1. Fast-Path: Greetings, Gratitude, Closings
        current_state_str = self.memory.get_state(session_id, "conversation_state", ConversationState.NO_ACTIVE_WORKFLOW.value)
        if current_state_str not in {ConversationState.FIR_QUESTIONNAIRE.value, ConversationState.COMPLAINT_QUESTIONNAIRE.value}:
            direct_reply = get_direct_conversational_reply(query)
            if direct_reply:
                intent, wflow, direct_answer = direct_reply
                self.memory.add_ai_message(session_id, direct_answer)
                self.memory.set_state(session_id, "workflow", None)
                self.memory.set_state(session_id, "conversation_state", ConversationState.NO_ACTIVE_WORKFLOW.value)
                return {
                    "success": True,
                    "intent": intent,
                    "workflow": wflow,
                    "category": "general",
                    "confidence": 0.99,
                    "response": direct_answer,
                    "sources": [],
                    "response_type": "advice",
                    "urgency": "none",
                    "actions": [],
                    "evidence_needed": [],
                    "next_action": "ask_question",
                }

        # 2. Extract Typed Entities deterministically
        deterministic_entities = self.entity_extractor.extract_deterministic(query)

        # 3. Update Case Profile V2
        profile_v2 = self.memory.get_case_profile_v2(session_id)
        if any(deterministic_entities.values()):
            profile_v2 = update_case_profile_v2(
                profile_v2,
                deterministic_entities,
                source="user_message",
                confidence=0.98,
                confirmed=False,
            )
            self.memory.set_case_profile(session_id, profile_v2)

        # 4. Pre-RAG Safety / Emergency Triage Layer
        emergency_plan = self.safety_agent.evaluate(query)

        # 5. Multilingual Query Analysis
        lang_profile = MultilingualProcessor.analyze_query(query)

        # 6. Intent & Category Detection (in parallel with deep extraction if needed)
        try:
            intent_data = self.intent_agent.detect(query)
        except Exception as intent_err:
            logger.warning(f"Intent detection failed: {intent_err}")
            intent_data = {
                "intent": "advice",
                "category": emergency_plan.incident_category if emergency_plan.is_emergency else "general",
                "workflow": "advisor",
                "confidence": 0.85,
            }

        intent = intent_data.get("intent", "advice")
        workflow = intent_data.get("workflow", "advisor")
        category = emergency_plan.incident_category if emergency_plan.is_emergency else intent_data.get("category", "general")
        intent_conf = float(intent_data.get("confidence", 0.9))

        # 7. State Machine Evaluation & Dynamic Switching
        current_state = ConversationState(current_state_str) if current_state_str in ConversationState.__members__ else ConversationState.NO_ACTIVE_WORKFLOW
        transition = ConversationStateMachine.evaluate_transition(
            current_state=current_state,
            user_message=query,
            detected_intent=intent,
            detected_workflow=workflow,
            is_emergency=emergency_plan.is_emergency,
        )

        logger.info(
            f"State Transition for session {session_id}: {transition.current_state} -> {transition.next_state} (Reason: {transition.reason})"
        )
        self.memory.set_state(session_id, "conversation_state", transition.next_state.value)

        # ------------------------------------------------------------------
        # Workflow: FACT CONFIRMATION & FIR INITIATION
        # ------------------------------------------------------------------
        if transition.next_state == ConversationState.FACT_CONFIRMATION:
            query_lower = query.lower().strip()
            form = self.memory.get_state(session_id, "fir_form") or profile_v2.to_legacy_dict()

            # Case 1: User explicitly confirms facts
            if query_lower in {"yes", "correct", "haan", "sahi hai", "ho", "proceed", "done", "confirm", "generate"}:
                missing = [f for f in INCIDENT_REQUIREMENTS.get(form.get("incident_type", "general"), INCIDENT_REQUIREMENTS["general"])["required"] if not form.get(f) and not (f == "amount" and form.get("amount_lost"))]
                if not missing:
                    fir_draft = self.fir_agent.generate_fir(form)
                    self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_READY.value)
                    self.memory.set_state(session_id, "workflow", None)
                    self.memory.set_state(session_id, "fir_draft", fir_draft)
                    self.memory.add_ai_message(session_id, fir_draft)
                    return {
                        "success": True,
                        "intent": "complaint",
                        "workflow": "fir",
                        "category": category,
                        "confidence": 0.98,
                        "response": fir_draft,
                        "sources": [],
                        "response_type": "fir_draft",
                        "urgency": "standard",
                        "actions": ["Review and print your Police Complaint / FIR Draft", "Submit with evidence at your local Cyber Crime Police Station or cybercrime.gov.in"],
                        "evidence_needed": [],
                        "next_action": "download_pdf",
                    }
                else:
                    self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_QUESTIONNAIRE.value)
                    self.memory.set_state(session_id, "workflow", "fir")
                    self.memory.set_state(session_id, "fir_form", form)
                    current_field = missing[0]
                    self.memory.set_state(session_id, "current_field", current_field)
                    next_q = FIELD_QUESTION_MAP.get(current_field, f"Please provide your {current_field.replace('_', ' ')}.")
                    self.memory.add_ai_message(session_id, next_q)
                    return {
                        "success": True,
                        "intent": "complaint",
                        "workflow": "fir",
                        "category": category,
                        "confidence": 0.95,
                        "response": next_q,
                        "sources": [],
                        "response_type": "fir_questionnaire",
                        "urgency": "standard",
                        "actions": [],
                        "evidence_needed": [],
                        "next_action": "answer_question",
                    }

            # Case 2: User initiating FIR workflow -> Extract from conversation history!
            all_messages = self.memory.get_messages(session_id) or []
            if not all_messages:
                db_conn = self.memory._get_db()
                try:
                    all_messages = db_conn.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id.asc()).all()
                except Exception:
                    all_messages = []
                finally:
                    db_conn.close()

            fir_data = self.fir_extractor.extract_from_conversation(
                messages=all_messages,
                session_id=session_id,
                existing_profile=profile_v2.to_legacy_dict(),
            )
            form = fir_data.to_legacy_form()
            self.memory.set_state(session_id, "fir_data", fir_data.model_dump())
            self.memory.set_state(session_id, "fir_form", form)
            self.memory.set_case_profile(session_id, form)

            summary = format_extracted_summary(fir_data)
            missing = fir_data.missing_fields

            if missing:
                # Ask ONLY the first genuinely missing field!
                current_field = missing[0]
                next_q_text = FIELD_QUESTION_MAP.get(current_field, f"Please provide your {current_field.replace('_', ' ')}.")
                has_meaningful_facts = bool(
                    fir_data.financial.amount.value
                    or fir_data.financial.transaction_id.value
                    or fir_data.incident.date.value
                    or (fir_data.incident.type.value and fir_data.incident.type.value != "unknown")
                )
                if has_meaningful_facts:
                    combined_question = f"{summary}\n\n**To complete your complaint:** {next_q_text}"
                else:
                    combined_question = next_q_text

                self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_QUESTIONNAIRE.value)
                self.memory.set_state(session_id, "workflow", "fir")
                self.memory.set_state(session_id, "current_field", current_field)
                self.memory.add_ai_message(session_id, combined_question)

                return {
                    "success": True,
                    "intent": "complaint",
                    "workflow": "fir",
                    "category": category,
                    "confidence": 0.95,
                    "response": combined_question,
                    "sources": [],
                    "response_type": "fir_questionnaire",
                    "urgency": "standard",
                    "actions": [],
                    "evidence_needed": [],
                    "next_action": "answer_question",
                }

            # If all required fields are already available, present confirmation summary!
            confirmation_text = format_confirmation_summary(fir_data)
            self.memory.add_ai_message(session_id, confirmation_text)
            return {
                "success": True,
                "intent": "complaint",
                "workflow": "fir",
                "category": category,
                "confidence": 0.98,
                "response": confirmation_text,
                "sources": [],
                "response_type": "fact_confirmation",
                "urgency": "standard",
                "actions": ["Review and confirm incident facts"],
                "evidence_needed": [],
                "next_action": "confirm_facts",
            }

        # ------------------------------------------------------------------
        # Workflow: FIR QUESTIONNAIRE (Single Question at a Time)
        # ------------------------------------------------------------------
        if transition.next_state == ConversationState.FIR_QUESTIONNAIRE:
            if transition.reason == "side_question_during_workflow":
                # Handle informational inquiry without corrupting active form
                rag_res = self.retrieval_agent.handle(query, history=history)
                side_answer = rag_res.get("answer", "") if isinstance(rag_res, dict) else str(rag_res)
                current_field = self.memory.get_state(session_id, "current_field", "")
                resumed_msg = f"{side_answer}\n\n---\n*Continuing your complaint draft:* Please provide **{current_field.replace('_', ' ')}** when ready."
                self.memory.add_ai_message(session_id, resumed_msg)
                return {
                    "success": True,
                    "intent": "retrieval",
                    "workflow": "fir",
                    "category": category,
                    "confidence": 0.95,
                    "response": resumed_msg,
                    "sources": rag_res.get("sources", []) if isinstance(rag_res, dict) else [],
                    "response_type": "advice",
                    "urgency": "standard",
                    "actions": [],
                    "evidence_needed": [],
                    "next_action": "answer_question",
                }

            res = self.fir_orchestrator.continue_workflow(
                session_id=session_id,
                answer=query,
            )

            if res.status == "ready":
                self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_READY.value)
                self.memory.set_state(session_id, "workflow", None)
                self.memory.set_state(session_id, "current_field", None)
                answer = res.fir or ""
                resp_type = "fir_draft"
                next_act = "download_pdf"
            elif res.status == "ready_for_confirmation":
                self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_QUESTIONNAIRE.value)
                self.memory.set_state(session_id, "workflow", "fir_confirmation")
                answer = res.next_question or "Please confirm these details."
                resp_type = "fact_confirmation"
                next_act = "confirm_facts"
            else:
                self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_QUESTIONNAIRE.value)
                self.memory.set_state(session_id, "current_field", res.current_field)
                answer = res.next_question or ""
                resp_type = "fir_questionnaire"
                next_act = "answer_question"

            self.memory.add_ai_message(session_id, answer)
            return {
                "success": True,
                "intent": "complaint",
                "workflow": "fir",
                "category": category,
                "confidence": 1.0,
                "response": answer,
                "sources": [],
                "response_type": resp_type,
                "urgency": "standard",
                "actions": [],
                "evidence_needed": [],
                "next_action": next_act,
            }

        # ------------------------------------------------------------------
        # Workflow: EMERGENCY TRIAGE & ADVISORY (Pre-RAG Triage Activated)
        # ------------------------------------------------------------------
        if emergency_plan.is_emergency or transition.next_state == ConversationState.SAFETY_EMERGENCY:
            # 1. Retrieve supporting official regulatory guidelines
            retrieved_chunks = self.retrieval_agent.ai.pipeline.retrieve(
                query=lang_profile.canonical_query_en,
                top_k=4,
            )
            sources = self.retrieval_agent.ai.pipeline.build_sources(retrieved_chunks)

            # 2. Format Structured Response with Urgent Actions at the Top
            legal_info = (
                f"Under official Reserve Bank of India (RBI) citizen protection guidelines and IT Act provisions, "
                f"immediate notification to financial intermediaries enables quick alert broadcasting to beneficiary institutions."
            )
            structured_resp = ResponseFormatter.format_incident_response(
                summary_explanation=emergency_plan.safe_explanation,
                actions=emergency_plan.immediate_actions,
                evidence_items=emergency_plan.evidence_to_preserve,
                legal_info=legal_info,
                next_step=emergency_plan.single_next_question,
                urgency=emergency_plan.urgency_level,
                language=lang_profile.target_response_language,
                why_it_matters="Swift containment prevents further unauthorized access, stops secondary financial transfers, and secures digital records needed for legal reporting.",
            )

            # 3. Verifier Agent Audit
            user_facts = {"amount": profile_v2.financial.amount}
            verification = self.verifier_agent.verify(
                query=query,
                response_text=structured_resp.markdown_text,
                retrieved_contexts=retrieved_chunks,
                user_facts=user_facts,
                intent_confidence=0.98,
                retrieval_confidence=0.92,
            )

            final_answer = verification.sanitized_response
            self.memory.add_ai_message(session_id, final_answer)
            self.memory.set_state(session_id, "workflow", "advisor")
            self.memory.set_state(session_id, "category", category)

            return {
                "success": True,
                "intent": "emergency",
                "workflow": "advisor",
                "category": category,
                "confidence": verification.verification_score,
                "response": final_answer,
                "sources": sources,
                "response_type": "emergency",
                "urgency": emergency_plan.urgency_level.lower(),
                "actions": emergency_plan.immediate_actions,
                "evidence_needed": emergency_plan.evidence_to_preserve,
                "next_action": emergency_plan.single_next_question,
                "verification": {
                    "is_verified": verification.is_verified,
                    "grounding_score": verification.grounding_score,
                    "verification_score": verification.verification_score,
                    "confidence_breakdown": verification.confidence_breakdown,
                },
            }

        # ------------------------------------------------------------------
        # Workflow: STANDARD HYBRID RAG / ADVISORY
        # ------------------------------------------------------------------
        if workflow == "rag" or intent == "retrieval":
            rag_result = self.retrieval_agent.handle(lang_profile.canonical_query_en, history=history)
            if isinstance(rag_result, dict):
                raw_answer = rag_result.get("answer", "")
                sources = rag_result.get("sources", [])
            else:
                raw_answer = str(rag_result)
                sources = []

            verification = self.verifier_agent.verify(
                query=query,
                response_text=raw_answer,
                retrieved_contexts=sources,
                user_facts=None,
                intent_confidence=intent_conf,
                retrieval_confidence=0.90,
            )

            final_answer = verification.sanitized_response
            self.memory.add_ai_message(session_id, final_answer)
            self.memory.set_state(session_id, "workflow", "rag")

            return {
                "success": True,
                "intent": "retrieval",
                "workflow": "rag",
                "category": category,
                "confidence": verification.verification_score,
                "response": final_answer,
                "sources": sources,
                "response_type": "advice",
                "urgency": "standard",
                "actions": [],
                "evidence_needed": [],
                "next_action": "ask_question",
                "verification": {
                    "is_verified": verification.is_verified,
                    "grounding_score": verification.grounding_score,
                    "verification_score": verification.verification_score,
                    "confidence_breakdown": verification.confidence_breakdown,
                },
            }

        # Default Advisor flow
        advisor_result = self.advisor_agent.handle(
            message=lang_profile.canonical_query_en,
            category=category,
            history=history,
        )
        answer = advisor_result.get("response", "")
        sources = advisor_result.get("sources", [])

        verification = self.verifier_agent.verify(
            query=query,
            response_text=answer,
            retrieved_contexts=sources,
            user_facts={"amount": profile_v2.financial.amount},
            intent_confidence=intent_conf,
            retrieval_confidence=0.88,
        )

        final_answer = verification.sanitized_response
        self.memory.add_ai_message(session_id, final_answer)
        self.memory.set_state(session_id, "workflow", "advisor")
        self.memory.set_state(session_id, "category", category)

        return {
            "success": True,
            "intent": intent,
            "workflow": workflow,
            "category": category,
            "confidence": verification.verification_score,
            "response": final_answer,
            "sources": sources,
            "response_type": "advice",
            "urgency": "standard",
            "actions": [],
            "evidence_needed": [],
            "next_action": "prepare_complaint",
            "verification": {
                "is_verified": verification.is_verified,
                "grounding_score": verification.grounding_score,
                "verification_score": verification.verification_score,
                "confidence_breakdown": verification.confidence_breakdown,
            },
        }

    def handle_stream(self, session_id: str, query: str):
        """
        Yields Server-Sent Events (SSE) JSON payloads with token streaming.
        """
        # Run standard handle logic for safety triage and structured metadata
        res = self.handle(session_id, query)
        payload = {
            "token": res.get("response", ""),
            "done": True,
            "intent": res.get("intent", "advice"),
            "workflow": res.get("workflow", "advisor"),
            "category": res.get("category", "general"),
            "sources": res.get("sources", []),
            "response_type": res.get("response_type", "advice"),
            "urgency": res.get("urgency", "standard"),
            "actions": res.get("actions", []),
            "evidence_needed": res.get("evidence_needed", []),
            "next_action": res.get("next_action", ""),
        }
        yield f"data: {json.dumps(payload)}\n\n"

    def start_fir_from_entities(self, session_id: str, entities: dict):
        form = self.fir_agent.get_empty_form()
        form = self.fir_agent.merge_agent.merge(form, entities)
        missing = self.fir_agent.get_missing_fields(form)

        self.memory.set_state(session_id, "workflow", "fir")
        self.memory.set_state(session_id, "fir_form", form)

        if missing:
            current_field = missing[0]
            self.memory.set_state(session_id, "current_field", current_field)
            self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_QUESTIONNAIRE.value)
            return {
                "success": True,
                "workflow": "fir",
                "status": "incomplete",
                "current_field": current_field,
                "response": self.fir_agent.generate_next_question(missing),
            }

        fir = self.fir_agent.generate_fir(form)
        self.memory.set_state(session_id, "workflow", None)
        self.memory.set_state(session_id, "fir_form", None)
        self.memory.set_state(session_id, "current_field", None)
        self.memory.set_state(session_id, "conversation_state", ConversationState.FIR_READY.value)

        return {
            "success": True,
            "workflow": "fir",
            "status": "ready",
            "response": fir,
        }

    def get_case_profile(self, session_id: str) -> dict:
        return self.memory.get_case_profile(session_id)

    def update_case_profile(self, session_id: str, data: dict) -> dict:
        profile_v2 = self.memory.get_case_profile_v2(session_id)
        profile_v2 = update_case_profile_v2(profile_v2, data, source="user_message")
        self.memory.set_case_profile(session_id, profile_v2)
        return profile_v2.to_legacy_dict()