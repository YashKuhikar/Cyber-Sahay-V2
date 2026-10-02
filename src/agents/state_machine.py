from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    NO_ACTIVE_WORKFLOW = "NO_ACTIVE_WORKFLOW"
    SAFETY_EMERGENCY = "SAFETY_EMERGENCY"
    ADVICE = "ADVICE"
    FOLLOW_UP = "FOLLOW_UP"
    FACT_CONFIRMATION = "FACT_CONFIRMATION"
    FIR_QUESTIONNAIRE = "FIR_QUESTIONNAIRE"
    FIR_READY = "FIR_READY"
    COMPLAINT_QUESTIONNAIRE = "COMPLAINT_QUESTIONNAIRE"
    COMPLAINT_READY = "COMPLAINT_READY"
    EVIDENCE_ANALYSIS = "EVIDENCE_ANALYSIS"


class WorkflowTransition(BaseModel):
    current_state: ConversationState
    next_state: ConversationState
    reason: str
    target_workflow: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationStateMachine:
    """
    Manages workflow transitions and prevents stale agent states
    from intercepting unrelated user queries.
    """

    TRANSITION_TRIGGERS = {
        "fir": ["file an fir", "generate fir", "draft fir", "police complaint", "report to police", "fir draft", "fir banado"],
        "complaint": ["bank complaint", "complaint letter", "draft email", "application to bank", "dispute transaction"],
        "cancel": ["cancel", "stop", "nevermind", "quit", "start over", "leave it", "nahi chahiye", "rehne do"],
        "rag_inquiry": ["what is", "what are", "explain", "kya hota hai", "meaning of", "define", "section "],
    }

    @classmethod
    def evaluate_transition(
        cls,
        current_state: ConversationState,
        user_message: str,
        detected_intent: str,
        detected_workflow: str,
        is_emergency: bool = False,
    ) -> WorkflowTransition:
        msg = user_message.strip().lower()

        # 1. User wants to cancel active workflow
        if any(trig in msg for trig in cls.TRANSITION_TRIGGERS["cancel"]):
            return WorkflowTransition(
                current_state=current_state,
                next_state=ConversationState.NO_ACTIVE_WORKFLOW,
                reason="user_cancellation",
                target_workflow="none",
            )

        # 2. Urgent Emergency override
        if is_emergency and current_state != ConversationState.SAFETY_EMERGENCY:
            return WorkflowTransition(
                current_state=current_state,
                next_state=ConversationState.SAFETY_EMERGENCY,
                reason="emergency_detected",
                target_workflow="safety",
            )

        # 3. Explicit switch to Police Complaint / FIR
        if any(trig in msg for trig in cls.TRANSITION_TRIGGERS["fir"]) or (detected_intent == "complaint" and detected_workflow == "fir"):
            return WorkflowTransition(
                current_state=current_state,
                next_state=ConversationState.FACT_CONFIRMATION,
                reason="switch_to_fir",
                target_workflow="fir",
            )

        # 4. Explicit switch to Bank / Portal Complaint
        if any(trig in msg for trig in cls.TRANSITION_TRIGGERS["complaint"]) or (detected_intent == "complaint" and detected_workflow == "complaint"):
            return WorkflowTransition(
                current_state=current_state,
                next_state=ConversationState.FACT_CONFIRMATION,
                reason="switch_to_complaint",
                target_workflow="complaint",
            )

        # 5. Explanatory Question during Questionnaire (Do not treat as questionnaire answer!)
        if current_state in {ConversationState.FIR_QUESTIONNAIRE, ConversationState.COMPLAINT_QUESTIONNAIRE}:
            if any(msg.startswith(trig) or f" {trig} " in msg for trig in cls.TRANSITION_TRIGGERS["rag_inquiry"]):
                return WorkflowTransition(
                    current_state=current_state,
                    next_state=current_state,  # Pause state without losing form progress
                    reason="side_question_during_workflow",
                    target_workflow="rag",
                )

        # 6. Default progression
        if current_state == ConversationState.NO_ACTIVE_WORKFLOW:
            if detected_workflow in {"fir", "complaint"}:
                return WorkflowTransition(
                    current_state=current_state,
                    next_state=ConversationState.FACT_CONFIRMATION,
                    reason="workflow_initiation",
                    target_workflow=detected_workflow,
                )
            elif is_emergency:
                return WorkflowTransition(
                    current_state=current_state,
                    next_state=ConversationState.SAFETY_EMERGENCY,
                    reason="emergency_advisory",
                    target_workflow="safety",
                )
            else:
                return WorkflowTransition(
                    current_state=current_state,
                    next_state=ConversationState.ADVICE,
                    reason="advice_request",
                    target_workflow="advisor",
                )

        if current_state in {ConversationState.ADVICE, ConversationState.SAFETY_EMERGENCY}:
            return WorkflowTransition(
                current_state=current_state,
                next_state=ConversationState.FOLLOW_UP,
                reason="follow_up_conversation",
                target_workflow="advisor",
            )

        return WorkflowTransition(
            current_state=current_state,
            next_state=current_state,
            reason="continue_current_state",
            target_workflow=detected_workflow,
        )
