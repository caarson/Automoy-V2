"""
Data models for Automoy core system.

This module defines the data structures used throughout the Automoy application
for managing operator state, status tracking, and communication between components.
"""

from enum import Enum
from typing import List, Optional, Any, Dict
from dataclasses import dataclass


class AutomoyStatus(Enum):
    """Enumeration of possible Automoy operator status states."""
    IDLE = "idle"
    OBJECTIVE_SET = "objective_set"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class OperatorState:
    """Data class representing the current state of the Automoy operator."""
    status: AutomoyStatus = AutomoyStatus.IDLE
    goal: Optional[str] = None
    objective: Optional[str] = None
    parsed_steps: Optional[List[Dict[str, Any]]] = None
    current_step_index: int = -1
    errors: List[str] = None
    last_action_summary: Optional[str] = None
    consecutive_error_count: int = 0
    
    def __post_init__(self):
        """Initialize mutable default values."""
        if self.errors is None:
            self.errors = []
        if self.parsed_steps is None:
            self.parsed_steps = []
