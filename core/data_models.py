"""
Data models for Automoy core system.

This module defines the data structures used throughout the Automoy application
for managing operator state, status tracking, and communication between components.
"""

import json
import os
from enum import Enum
from typing import List, Optional, Any, Dict, Tuple
from dataclasses import dataclass, field

# --- File paths for state management ---
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "gui_state.json")
GOAL_REQUEST_FILE = os.path.join(os.path.dirname(__file__), "..", "goal_request.json")


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
    STOPPED = "stopped"


@dataclass
class OperatorState:
    """Data class representing the current state of the Automoy operator."""
    status: AutomoyStatus = AutomoyStatus.IDLE
    goal: Optional[str] = None
    objective: Optional[str] = None
    parsed_steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step_index: int = -1
    errors: List[str] = field(default_factory=list)
    last_action_summary: Optional[str] = None
    consecutive_error_count: int = 0

# --- Added Placeholder Definitions ---
@dataclass
class VisualElement:
    id: str
    description: str
    coordinates: Optional[Tuple[int, int, int, int]] = None # (x1, y1, x2, y2)
    label: Optional[str] = None

@dataclass
class Step:
    step_id: str
    action: str # e.g., "click", "type", "read"
    target_element_id: Optional[str] = None # ID of a VisualElement
    target_coordinates: Optional[Tuple[int, int]] = None # (x,y) for clicks if no element
    value: Optional[str] = None # e.g., text to type, value to select
    description: Optional[str] = None
    screenshot_before: Optional[str] = None # path to screenshot
    screenshot_after: Optional[str] = None # path to screenshot
    status: str = "pending" # pending, executing, completed, error
    error_message: Optional[str] = None

@dataclass
class Operation: # This was used in prompts, might be similar to a Step or a sequence of Steps
    operation_id: str
    description: str
    tool_name: Optional[str] = None # e.g., "mouse_click", "keyboard_type"
    tool_args: Dict[str, Any] = field(default_factory=dict)
    # Example tool_args:
    # For mouse_click: {"x": 100, "y": 200, "button": "left"}
    # For keyboard_type: {"text": "hello world", "press_enter": True}

@dataclass
class Objective: # Represents the LLM-formulated objective
    id: str
    text: str
    status: str = "pending" # pending, in_progress, completed, error
    steps: List[Step] = field(default_factory=list)
    raw_llm_response: Optional[str] = None

@dataclass
class FormulatedObjective: # Used in JSBridge and GUI updates
    objective_text: str
    error_message: Optional[str] = None # If LLM failed to formulate

@dataclass
class LLMResponse: # Generic LLM response structure
    content: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[Any] = None # To store the full API response if needed

@dataclass
class LLMFormattedResponse: # Specifically for formatted LLM output like JSON
    parsed_data: Optional[Dict[str, Any]] = None # For JSON objects
    parsed_list: Optional[List[Any]] = None # For JSON arrays
    error: Optional[str] = None
    raw_response: Optional[str] = None

@dataclass
class GoalUpdateRequest: # For /update_goal endpoint in GUI
    goal: str
    timestamp: float

@dataclass
class StatusUpdateRequest: # For /update_status endpoint in GUI (if needed by core)
    status: str
    message: Optional[str] = None
    # Potentially other fields like progress, current_step_description, etc.

@dataclass
class ObjectiveUpdateRequest: # For /update_objective endpoint in GUI (if needed by core)
    objective: str
    # Potentially other fields

@dataclass
class MainLoopState: # Represents the overall state managed by the main async loop
    current_goal: Optional[str] = None
    last_goal_timestamp: float = 0.0
    processed_goal_text: Optional[str] = None # The goal text that has been sent for objective formulation
    processed_goal_timestamp: float = 0.0
    current_objective: Optional[Objective] = None # The active objective being worked on
    operator_state: OperatorState = field(default_factory=OperatorState)
    # Potentially other high-level state variables
    # e.g., llm_operational: bool = True
    # e.g., omniparser_operational: bool = True

# --- End Placeholder Definitions ---

# --- State Management Functions ---
def get_initial_state():
    """Return the initial state for the GUI."""
    return {
        "operator_status": "initializing",
        "objective": "System starting up...",
        "current_step_details": "Initializing components...",
        "operations_log": [],
        "llm_error_message": None
    }

def read_state():
    """Read the current state from the GUI state file."""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return a default structure if file doesn't exist or is corrupt
        return get_initial_state()

def write_state(state_dict):
    """Write the state to the GUI state file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state_dict, f, indent=2)
    except Exception as e:
        print(f"Error writing state file: {e}")

# Define missing types for compatibility
AutomoyState = OperatorState  # Alias for backward compatibility
GUIState = dict  # GUI state is just a dictionary
ExecutionState = dict  # Execution state is just a dictionary
