"""
Core package for the Shufti.jp job automation agent.

This package contains the central components that orchestrate the agent's operation,
including the main agent class, workflow management, and memory systems.

The core package serves as the central nervous system of the agent, coordinating
between the specialized modules to create a coherent automation workflow.
"""

from core.agent import ShuftiAgent
from core.workflow_manager import WorkflowManager
from core.memory import AgentMemory

__version__ = '0.1.0'