from .coordinator_agent import CoordinatorAgent
from ..memory.shared_memory import memory

coordinator = CoordinatorAgent(memory=memory)