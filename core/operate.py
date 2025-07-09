import json
import re
import asyncio
import os
import pathlib
import socket
import sys
import psutil
import requests
import logging # Import logging
import platform # Add this import
import time # ADDED
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Coroutine, Tuple # MODIFIED

from core.exceptions import AutomoyError, OperationError
from core.utils.operating_system.os_interface import OSInterface
from core.utils.operating_system.desktop_utils import DesktopUtils
from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.lm.lm_interface import MainInterface as LLMInterface, handle_llm_response
from core.prompts.prompts import (
    VISUAL_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE,
    THINKING_PROCESS_SYSTEM_PROMPT, 
    THINKING_PROCESS_USER_PROMPT_TEMPLATE, 
    STEP_GENERATION_SYSTEM_PROMPT, 
    STEP_GENERATION_USER_PROMPT_TEMPLATE, 
    ACTION_GENERATION_SYSTEM_PROMPT,
    ACTION_GENERATION_USER_PROMPT_TEMPLATE,
)
from config import Config
from core.utils.operating_system.desktop_utils import DesktopUtils
from core.data_models import AutomoyStatus, OperatorState # Ensure these are imported

# Get a logger for this module
logger = logging.getLogger(__name__)

# Ensure the project root is added to the Python path
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) # Already there, but ensure it's correct

# Add the project root to the Python path if this script is run directly
if __name__ == "__main__" and (__package__ is None or __package__ == ''):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Define Project Root for operate.py
OPERATE_PY_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_SCREENSHOT_FILENAME = "automoy_current.png" # Relative to project root
PROCESSED_SCREENSHOT_RELATIVE_PATH = pathlib.Path("core") / "utils" / "omniparser" / "processed_screenshot.png"

# Adjust imports to use absolute paths consistently
from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.utils.operating_system.os_interface import OSInterface

# Optional imports - these features will be disabled if modules are not available
try:
    from core.utils.vmware.vmware_interface import VMWareInterface
    VMWARE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: VMware functionality not available: {e}")
    VMWareInterface = None
    VMWARE_AVAILABLE = False

try:
    from core.utils.web_scraping.webscrape_interface import WebScrapeInterface
    WEB_SCRAPING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Web scraping functionality not available: {e}")
    WebScrapeInterface = None
    WEB_SCRAPING_AVAILABLE = False

from core.utils.region.mapper import map_elements_to_coords
# from core.prompts.prompts import get_system_prompt # get_system_prompt is imported below with others

# 👉 Integrated LLM interface (merged MainInterface + handle_llm_response) - imported above
from core.environmental.anchor.desktop_anchor_point import show_desktop
from core.utils.operating_system.desktop_utils import DesktopUtils # Added

# Config import - ensure this path is robust
# Assuming config is in the parent directory of core
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "config"))
from config import Config


# Define BASE64_RE at the module level
BASE64_RE = re.compile(r'^[A-Za-z0-9+/=\\s]{100,}$')

def clean_json_data(obj): # Renamed to avoid conflict if defined elsewhere
    """Recursively remove long base64-like strings from a JSON-like structure."""
    if isinstance(obj, dict):
        return {k: clean_json_data(v) for k, v in obj.items() if not (isinstance(v, str) and BASE64_RE.match(v))}
    elif isinstance(obj, list):
        return [clean_json_data(elem) for elem in obj]
    # Removed string cleaning part that was too aggressive, OmniParser should return clean text.
    # If specific string cleaning is needed, it should be more targeted.
    else:
        return obj

# Function to check if a port is in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# Function to check if a process with a specific name is running
def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False

# Helper function to update GUI state (moved to module level for broader access if needed)
async def _update_gui_state(endpoint: str, payload: dict):
    """Helper to asynchronously send state updates to the GUI."""
    try:
        # Ensure the endpoint starts with a slash
        if not endpoint.startswith("/"):
            url_endpoint = f"/state/{endpoint}" # Default to /state/ if not a full path
        else:
            url_endpoint = endpoint

        url = f"http://127.0.0.1:8000{url_endpoint}"
        
        loop = asyncio.get_event_loop()
        # Using lambda to capture current payload value for the executor thread
        current_payload = payload 
        # Ensure payload is not None, default to empty dict if it is, to satisfy requests.post
        response = await loop.run_in_executor(None, lambda: requests.post(url, json=current_payload if current_payload is not None else {}, timeout=5))
        
        if response.status_code == 200:
            logger.debug(f"[GUI_UPDATE] Successfully sent payload to {url}. Response status: {response.status_code}, text: {response.text[:100] if response.text else 'N/A'}")
        else:
            # For 422 errors, log more of the response to see validation details
            if response.status_code == 422:
                logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text}")
            else:
                logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text[:200] if response.text else 'N/A'}")
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to update GUI state at {url} (RequestException): {e}")
    except Exception as e:
        logger.error(f"Unexpected error in _update_gui_state sending to {url}: {e}", exc_info=True)

class AutomoyOperator:
    """Central orchestrator for Automoy autonomous operation."""
    def __init__(self, 
                 stop_event=None,
                 webview_window=None,
                 gui_host="127.0.0.1",
                 gui_port=8000,
                 objective: str = "",
                 pause_event: asyncio.Event = None
                 ):
        self.config = Config() # Instantiate Config internally
        logger.info(f"AutomoyOperator initialized. Using internal Config instance. DEBUG_MODE from internal config: {self.config.get('DEBUG_MODE', 'Not Set')}")

        self.stop_event = stop_event
        self.webview_window = webview_window
        self.gui_host = gui_host
        self.gui_port = gui_port
        self.objective = objective
        self.pause_event = pause_event if pause_event else asyncio.Event()
        
        # These will be initialized later or as needed
        self.manage_gui_window_func = None
        self.omniparser = None
        self._update_gui_state_func = None
        
        # MainInterface doesn't take params, it loads config itself
        self.llm_interface = LLMInterface()
        logger.info(f"LLM Interface (MainInterface) initialized with internal configuration")
        
        self.steps = []  # List[Dict[str, Any]]
        self.steps_for_gui = []  # List[Dict[str, Any]]
        self.executed_steps = []  # List[Dict[str, Any]]
        
        self.current_step_index = 0  # int
        
        # NEW: Visual context management - do visual analysis ONCE per goal
        self.initial_screenshot_path = None  # Screenshot taken ONCE at start
        self.initial_processed_screenshot_path = None  # Processed screenshot from initial analysis
        self.saved_visual_context = None  # Visual analysis done ONCE and saved
        self.context_requests = []  # Track LLM requests for additional context
        
        # Legacy fields for backward compatibility (but will be managed differently)
        self.current_screenshot_path = None  # Optional[Path]
        self.current_processed_screenshot_path = None  # Optional[Path]
        self.visual_analysis_output = None  # Optional[str]
        self.thinking_process_output = None  # Optional[str]
        self.operations_generated_for_gui = []  # List[Dict[str, str]]
        self.last_action_summary = None  # Optional[str]

        self.max_retries_per_step = self.config.get_max_retries_per_step()
        self.max_consecutive_errors = self.config.get_max_consecutive_errors()
        self.consecutive_error_count = 0
        
        # Operation task tracking
        self._operation_task = None
        
        self.session_id = f"automoy-op-{int(time.time())}"
        logger.info(f"AutomoyOperator initialized with session ID: {self.session_id}")
        logger.info(f"Objective: {self.objective}")
        # Log omniparser type
        if self.omniparser is None:
            logger.warning("OmniParser is not initialized yet (None)")
        else:
            logger.debug(f"OmniParser interface type: {type(self.omniparser)}")
            if not hasattr(self.omniparser, 'get_analysis'):
                logger.error("OmniParser interface does not have 'get_analysis' method!")
                # Potentially raise an error or handle this state
                # For now, logging it. This could be a source of issues if not addressed.

        # Initialize OS interface for executing operations
        self.os_interface = OSInterface()
        logger.info("OS Interface initialized for operation execution")

    def set_objective(self, objective: str):
        """Set the objective for the operator and start the operation loop."""
        logger.info(f"Setting new objective: {objective}")
        self.objective = objective
        
        # Start the operation loop in the background
        if self._operation_task is not None and not self._operation_task.done():
            logger.warning("Previous operation task is still running, cancelling it")
            self._operation_task.cancel()
        
        # Create and start new operation task
        loop = asyncio.get_event_loop()
        self._operation_task = loop.create_task(self.operate_loop())
        logger.info("Operation loop task created and started")

    async def _perform_visual_analysis(self, screenshot_path: Path, task_context: str) -> Tuple[Optional[Path], Optional[str]]:
        logger.info(f"Performing visual analysis for task: {task_context} on screenshot: {screenshot_path}")
        processed_screenshot_path: Optional[Path] = None
        analysis_results_json_str: Optional[str] = None # Initialize
        try:
            # Ensure omniparser is available and has the parse_screenshot method
            if not self.omniparser or not hasattr(self.omniparser, 'parse_screenshot'): # MODIFIED
                logger.error("OmniParser is not available or misconfigured (missing 'parse_screenshot').") # MODIFIED
                await self._update_gui_state_func("/state/visual", {"text": "Error: OmniParser not available or misconfigured."}) # MODIFIED (endpoint and payload key)
                return None, None

            logger.info(f"Calling omniparser.parse_screenshot for {screenshot_path}")
            
            # Add debug checks
            if not os.path.exists(screenshot_path):
                logger.error(f"Screenshot file does not exist: {screenshot_path}")
                await self._update_gui_state_func("/state/visual", {"text": "Error: Screenshot file not found."})
                return None, None
            
            file_size = os.path.getsize(screenshot_path)
            logger.info(f"Screenshot file size: {file_size} bytes")
            
            # Check if OmniParser server is responsive
            logger.info("Checking OmniParser server status before parsing...")
            if not self.omniparser._check_server_ready():
                logger.error("OmniParser server is not ready or not responding")
                await self._update_gui_state_func("/state/visual", {"text": "Error: OmniParser server not ready."})
                return None, None
            
            logger.info("OmniParser server is ready, proceeding with parsing...")
            
            # Capture any stdout from OmniParser interface for debugging
            import io
            import contextlib
            
            captured_output = io.StringIO()
            try:
                with contextlib.redirect_stdout(captured_output):
                    parsed_data = self.omniparser.parse_screenshot(str(screenshot_path))
                
                # Log the captured output from OmniParser
                omniparser_output = captured_output.getvalue()
                if omniparser_output:
                    logger.info(f"OmniParser debug output: {omniparser_output}")
                
            except Exception as parse_exception:
                logger.error(f"Exception during omniparser.parse_screenshot: {parse_exception}", exc_info=True)
                parsed_data = None

            if not parsed_data:
                logger.error("OmniParser failed to parse screenshot or returned no data.")
                
                # Provide detailed fallback information for user
                fallback_info = {
                    "error": "Visual analysis failed",
                    "reason": "OmniParser could not process the screenshot",
                    "fallback": "Proceeding with basic screen information",
                    "screenshot_path": str(screenshot_path),
                    "file_size": f"{file_size} bytes" if 'file_size' in locals() else "unknown"
                }
                
                # Create a basic fallback analysis
                fallback_analysis = {
                    "coords": [],
                    "parsed_content_list": [],
                    "error_info": fallback_info,
                    "timestamp": time.time(),
                    "status": "failed_visual_analysis"
                }
                
                analysis_results_json_str = json.dumps(fallback_analysis)
                
                await self._update_gui_state_func("/state/visual", {
                    "text": f"Visual analysis failed: {fallback_info['reason']}. Continuing with limited capabilities."
                })
                
                # Return the fallback analysis instead of None to allow the operator to continue
                logger.warning("Returning fallback analysis data to allow operator to continue with limited visual capabilities")
                return screenshot_path, analysis_results_json_str  # Use original screenshot path as fallback
            
            logger.info(f"OmniParser returned data with keys: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'not a dict'}")

            analysis_results_json_str = json.dumps(parsed_data) # MODIFIED
            
            internal_processed_path = OPERATE_PY_PROJECT_ROOT / PROCESSED_SCREENSHOT_RELATIVE_PATH
            if internal_processed_path.exists():
                processed_screenshot_path = internal_processed_path
                logger.info(f"Processed screenshot available at: {processed_screenshot_path}")
                # Notify GUI that the processed screenshot (expected at gui/static/processed_screenshot.png) is ready
                logger.debug(f"Updating GUI about processed screenshot being ready (expected at /static/processed_screenshot.png)")
                await self._update_gui_state_func("/state/screenshot_processed", {}) # MODIFIED (endpoint and empty payload)
            else:
                logger.warning(f"Processed screenshot not found at expected internal path: {internal_processed_path}. GUI might not show it.")
                # Attempt to check the static path directly as a fallback for logging
                gui_static_processed_path = OPERATE_PY_PROJECT_ROOT.parent / "gui" / "static" / "processed_screenshot.png"
                if gui_static_processed_path.exists():
                    logger.info(f"Processed screenshot IS present in GUI static folder: {gui_static_processed_path}")
                    await self._update_gui_state_func("/state/screenshot_processed", {}) # MODIFIED (endpoint and empty payload)
                else:
                    logger.warning(f"Processed screenshot also not found in GUI static folder: {gui_static_processed_path}. Using original screenshot path as fallback for processed path.")
                processed_screenshot_path = screenshot_path # Fallback

            # Fix: Ensure analysis_results_json_str is properly converted to string before slicing
            analysis_preview = str(analysis_results_json_str)[:500] if analysis_results_json_str else 'None'
            logger.debug(f"Visual analysis from OmniParser (first 500 chars): {analysis_preview}...")
            
            # Use Visual Analysis Expert to interpret the OmniParser data
            logger.info("Using Visual Analysis Expert to interpret screen elements...")
            try:
                # Determine anchor point context
                anchor_context = ""
                desktop_anchor_enabled = self.config.get("DESKTOP_ANCHOR_POINT", False)
                logger.info(f"Desktop anchor point config value: {desktop_anchor_enabled}")
                if desktop_anchor_enabled:
                    anchor_context = "ANCHOR POINT CONTEXT: You are analyzing the Windows desktop. This screenshot was taken after a desktop anchor point was set, meaning all windows were minimized to show the desktop. Look for desktop elements like taskbar, desktop icons, Start menu, and system tray. If the task context involves keyboard actions like pressing the Windows key, look for evidence of those actions' results (e.g., Start menu opening)."
                    logger.info("Added desktop anchor context to visual analysis prompt")
                else:
                    logger.info("Desktop anchor point disabled, no anchor context added")
                
                system_prompt_visual = VISUAL_ANALYSIS_SYSTEM_PROMPT
                user_prompt_visual = self.llm_interface.construct_visual_analysis_prompt(
                    objective=task_context,
                    screenshot_elements=analysis_results_json_str or "No screen elements detected",
                    anchor_context=anchor_context
                )
                
                messages_visual = [
                    {"role": "system", "content": system_prompt_visual},
                    {"role": "user", "content": user_prompt_visual}
                ]
                
                # Call Visual Analysis Expert
                visual_expert_response, _, visual_error = await self.llm_interface.get_llm_response(
                    model=self.config.get_model(),
                    messages=messages_visual,
                    objective=task_context,
                    session_id=self.session_id,
                    response_format_type="visual_analysis_expert"
                )
                
                if visual_error:
                    logger.error(f"Visual Analysis Expert error: {visual_error}")
                    expert_analysis = f"Visual Analysis Expert error: {visual_error}. Raw data: {analysis_results_json_str[:200]}..."
                elif visual_expert_response:
                    expert_analysis = visual_expert_response
                    logger.info(f"Visual Analysis Expert completed analysis: {expert_analysis[:200]}...")
                else:
                    expert_analysis = f"Visual Analysis Expert provided no response. Raw data: {analysis_results_json_str[:200]}..."
                
                await self._update_gui_state_func("/state/visual", {"text": expert_analysis})
                self.visual_analysis_output = expert_analysis  # Store the expert analysis, not raw data
                
                # Restore GUI visibility after visual analysis
                logger.info("Visual analysis completed, restoring GUI visibility")
                await self.manage_gui_window_func("show")
                
                return processed_screenshot_path, expert_analysis
                
            except Exception as e:
                logger.error(f"Visual Analysis Expert failed: {e}")
                # Fallback to raw data
                await self._update_gui_state_func("/state/visual", {"text": analysis_results_json_str or "No visual analysis generated."})
                self.visual_analysis_output = analysis_results_json_str
                
                # Restore GUI visibility after fallback
                logger.info("Visual analysis fallback completed, restoring GUI visibility")
                await self.manage_gui_window_func("show")
                
                return processed_screenshot_path, analysis_results_json_str

        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            await self._update_gui_state_func("/state/visual", {"text": f"Error in visual analysis: {e}"}) # MODIFIED (endpoint and payload key)
            self.visual_analysis_output = None # Clear on error
            return None, None

    async def _perform_initial_visual_analysis(self, goal_context: str) -> bool:
        """
        NEW: Perform visual analysis ONCE per goal and save the context.
        This replaces the old pattern of taking screenshots repeatedly.
        """
        logger.info(f"🔍 Performing INITIAL visual analysis for goal: {goal_context}")
        await self._update_gui_state_func("/state/current_operation", {
            "operation": "Performing initial visual analysis (ONCE per goal)",
            "status": "visual_analysis",
            "step": "Taking screenshot and analyzing screen context"
        })
        
        try:
            # Check if desktop anchor point is enabled
            desktop_anchor_enabled = self.config.get("DESKTOP_ANCHOR_POINT", False)
            if desktop_anchor_enabled:
                logger.info("Desktop anchor point enabled. Showing desktop before visual analysis.")
                try:
                    DesktopUtils.show_desktop()
                    await asyncio.sleep(1.0)
                    logger.info("Desktop shown successfully as anchor point.")
                except Exception as e:
                    logger.warning(f"Failed to show desktop as anchor point: {e}. Continuing anyway.")
            
            # Capture the INITIAL screenshot for the entire goal
            await self.manage_gui_window_func("hide")
            await asyncio.sleep(0.5)
            screenshot_filename_prefix = f"automoy_goal_initial_{goal_context.replace(' ', '_')[:30]}"
            self.initial_screenshot_path = self.desktop_utils.capture_current_screen(filename_prefix=screenshot_filename_prefix)
            await self.manage_gui_window_func("show")
            await asyncio.sleep(0.5)
            
            if not self.initial_screenshot_path:
                logger.error("❌ Failed to capture initial screenshot for goal.")
                await self._update_gui_state_func("/state/visual", {"text": "Error: Failed to capture initial screenshot."})
                return False
            
            # Update GUI with the initial screenshot
            await self._update_gui_state_func("/state/screenshot", {"path": str(self.initial_screenshot_path)})
            logger.info(f"✅ Initial screenshot captured: {self.initial_screenshot_path}")
            
            # Perform the INITIAL visual analysis using OmniParser
            self.initial_processed_screenshot_path, raw_visual_data = await self._perform_visual_analysis(
                screenshot_path=self.initial_screenshot_path,
                task_context=f"Initial analysis for goal: {goal_context}"
            )
            
            if not raw_visual_data:
                logger.warning("⚠️ Initial visual analysis failed. Setting fallback context.")
                self.saved_visual_context = f"Visual analysis unavailable for goal: {goal_context}. Working with limited visual context."
                await self._update_gui_state_func("/state/visual", {"text": self.saved_visual_context})
                return False
            
            # Save the visual context for reuse throughout the goal
            self.saved_visual_context = raw_visual_data
            logger.info(f"✅ Initial visual context saved: {self.saved_visual_context[:200]}...")
            
            # Update legacy fields for backward compatibility
            self.current_screenshot_path = self.initial_screenshot_path
            self.current_processed_screenshot_path = self.initial_processed_screenshot_path
            self.visual_analysis_output = self.saved_visual_context
            
            await self._update_gui_state_func("/state/visual", {"text": self.saved_visual_context})
            logger.info("🎯 Initial visual analysis completed and context saved for goal")
            return True
            
        except Exception as e:
            logger.error(f"❌ Exception during initial visual analysis: {e}", exc_info=True)
            self.saved_visual_context = f"Error during initial visual analysis: {e}. Working with minimal context."
            await self._update_gui_state_func("/state/visual", {"text": self.saved_visual_context})
            return False

    async def _request_additional_context(self, context_request: str) -> Optional[str]:
        """
        NEW: Allow LLM to request specific additional context about the screen.
        This is called when the LLM needs more specific information.
        """
        logger.info(f"🤔 LLM requested additional context: {context_request}")
        
        # Track the context request
        self.context_requests.append({
            "request": context_request,
            "timestamp": time.time()
        })
        
        try:
            # Use the saved visual context to answer the specific question
            system_prompt = """You are a visual analysis expert. You have detailed information about a screenshot and need to answer a specific question about it."""
            
            user_prompt = f"""
            Based on the visual analysis data below, please answer this specific question: {context_request}
            
            Visual Analysis Data:
            {self.saved_visual_context or 'No visual context available'}
            
            Provide a focused, specific answer to the question. If the information is not available in the visual data, say so clearly.
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response, _, error = await self.llm_interface.get_llm_response(
                model=self.config.get_model(),
                messages=messages,
                objective=self.objective,
                session_id=self.session_id,
                response_format_type="context_response"
            )
            
            if error or not response:
                logger.warning(f"⚠️ Failed to get context response: {error}")
                return "Context information not available due to analysis error."
            
            logger.info(f"✅ Context response provided: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"❌ Exception getting additional context: {e}", exc_info=True)
            return f"Error retrieving context: {e}"

    async def _collaborative_step_generation(self, goal_context: str) -> bool:
        """
        NEW: Collaborative approach where thinking LLM can request context before generating steps.
        """
        logger.info(f"🧠 Starting collaborative step generation for: {goal_context}")
        await self._update_gui_state_func("/state/current_operation", {
            "operation": "Collaborative step generation with LLM",
            "status": "thinking",
            "step": "LLM analyzing goal and requesting context as needed"
        })
        
        try:
            # PHASE 1: Thinking LLM analyzes the goal and can request context
            thinking_system_prompt = """You are a strategic thinking AI that plans how to achieve UI automation goals.

You have access to initial visual context about the screen state. If you need more specific information about the screen (like specific icon positions, menu states, etc.), you can request it by including a line starting with "CONTEXT_REQUEST:" in your response.

Your job is to:
1. Analyze the goal and current screen state
2. Request any additional context you need
3. Provide strategic thinking for step generation

If you need specific context, use this format:
CONTEXT_REQUEST: [specific question about the screen]

Then continue with your thinking."""
            
            thinking_user_prompt = f"""
            Goal: {goal_context}
            
            Initial Visual Context:
            {self.saved_visual_context or 'No visual context available'}
            
            Please analyze this goal and provide strategic thinking. If you need more specific information about the screen state, request it using the CONTEXT_REQUEST format.
            """
            
            thinking_messages = [
                {"role": "system", "content": thinking_system_prompt},
                {"role": "user", "content": thinking_user_prompt}
            ]
            
            thinking_response, _, thinking_error = await self.llm_interface.get_llm_response(
                model=self.config.get_model(),
                messages=thinking_messages,
                objective=goal_context,
                session_id=self.session_id,
                response_format_type="collaborative_thinking"
            )
            
            if thinking_error or not thinking_response:
                logger.error(f"❌ Thinking LLM error: {thinking_error}")
                self.thinking_process_output = f"Error in thinking phase: {thinking_error}"
                await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                return False
            
            # Check if LLM requested additional context
            context_request = None
            if "CONTEXT_REQUEST:" in thinking_response:
                lines = thinking_response.split('\n')
                for line in lines:
                    if line.strip().startswith("CONTEXT_REQUEST:"):
                        context_request = line.replace("CONTEXT_REQUEST:", "").strip()
                        break
            
            # If context was requested, get it and re-run thinking
            if context_request:
                logger.info(f"🔍 LLM requested additional context: {context_request}")
                additional_context = await self._request_additional_context(context_request)
                
                # Re-run thinking with additional context
                enhanced_user_prompt = f"""
                Goal: {goal_context}
                
                Initial Visual Context:
                {self.saved_visual_context or 'No visual context available'}
                
                Additional Context (you requested): {additional_context}
                
                Now provide your complete strategic thinking for achieving this goal.
                """
                
                enhanced_messages = [
                    {"role": "system", "content": thinking_system_prompt.replace("If you need specific context, use this format:\nCONTEXT_REQUEST: [specific question about the screen]\n\nThen continue with your thinking.", "You now have all the context you need. Provide complete strategic thinking.")},
                    {"role": "user", "content": enhanced_user_prompt}
                ]
                
                thinking_response, _, thinking_error = await self.llm_interface.get_llm_response(
                    model=self.config.get_model(),
                    messages=enhanced_messages,
                    objective=goal_context,
                    session_id=self.session_id,
                    response_format_type="enhanced_thinking"
                )
                
                if thinking_error or not thinking_response:
                    logger.error(f"❌ Enhanced thinking LLM error: {thinking_error}")
                    self.thinking_process_output = f"Error in enhanced thinking: {thinking_error}"
                    await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                    return False
            
            # Save the thinking output
            self.thinking_process_output = thinking_response
            logger.info(f"✅ Collaborative thinking completed: {thinking_response[:200]}...")
            await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
            
            # PHASE 2: Generate steps using the thinking output and context
            return await self._generate_steps_with_context(goal_context)
            
        except Exception as e:
            logger.error(f"❌ Exception in collaborative step generation: {e}", exc_info=True)
            self.thinking_process_output = f"Exception in collaborative thinking: {e}"
            await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
            return False

    async def _generate_steps_with_context(self, goal_context: str) -> bool:
        """
        NEW: Generate steps using the collaborative thinking and saved visual context.
        """
        logger.info(f"📋 Generating steps with saved context for: {goal_context}")
        await self._update_gui_state_func("/state/current_operation", {
            "operation": "Generating actionable steps",
            "status": "step_generation",
            "step": "Converting thinking into specific UI actions"
        })
        
        try:
            system_prompt_steps = STEP_GENERATION_SYSTEM_PROMPT
            user_prompt_steps = f"""
            Goal: {goal_context}
            
            Strategic Thinking:
            {self.thinking_process_output or 'No thinking process available'}
            
            Visual Context (saved from initial analysis):
            {self.saved_visual_context or 'No visual context available'}
            
            Additional Context Requests Made: {len(self.context_requests)} requests
            
            Based on the strategic thinking and visual context, generate specific, actionable steps to achieve this goal.
            Each step should be a concrete UI action that can be executed.
            """
            
            messages_steps = [
                {"role": "system", "content": system_prompt_steps},
                {"role": "user", "content": user_prompt_steps}
            ]

            raw_llm_response, _, llm_error = await self.llm_interface.get_llm_response(
                model=self.config.get_model(),
                messages=messages_steps,
                objective=goal_context,
                session_id=self.session_id,
                response_format_type="step_generation" 
            )

            if llm_error:
                logger.error(f"❌ LLM error during step generation: {llm_error}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"LLM Error: {llm_error}"})
                return False
            
            if not raw_llm_response:
                logger.warning("⚠️ LLM returned no response for step generation.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM provided no response for steps."})
                return False

            # Parse the response into steps
            steps_text = handle_llm_response(raw_llm_response, "step_generation", is_json=False)
            logger.info(f"📝 Step generation response: {str(steps_text)[:200]}...")

            if isinstance(steps_text, dict) and "error" in steps_text:
                logger.error(f"❌ Step parsing error: {steps_text}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Step parsing error: {steps_text.get('message', 'Unknown error')}"})
                return False

            if not steps_text:
                logger.warning("⚠️ No steps parsed from LLM response.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to parse steps from LLM response."})
                return False
            
            # Parse the numbered list from plain text
            steps_lines = steps_text.strip().split('\n')
            parsed_steps = []
            
            for line in steps_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for numbered steps (1. 2. etc.) or steps with - or * 
                step_match = re.match(r'^(\d+\.|\d+\)|\*|-)\s*(.+)', line)
                if step_match:
                    step_description = step_match.group(2).strip()
                    parsed_steps.append({
                        "description": step_description,
                        "type": "action"
                    })
                elif line and not any(keyword in line.lower() for keyword in ['goal:', 'steps:', 'based on', 'guidelines:']):
                    # Include lines that look like steps but aren't numbered
                    parsed_steps.append({
                        "description": line.strip(),
                        "type": "action"
                    })
            
            if parsed_steps:
                self.steps = parsed_steps
                self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                logger.info(f"✅ Successfully parsed {len(parsed_steps)} steps from collaborative analysis")
                await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
                return True
            else:
                # If no numbered steps found, use entire response as single step
                logger.warning("⚠️ No numbered steps found, using entire response as single step")
                self.steps = [{"description": steps_text.strip(), "type": "action"}]
                self.steps_for_gui = [{"description": steps_text.strip()}]
                await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
                return True
                
        except Exception as e:
            logger.error(f"❌ Exception generating steps with context: {e}", exc_info=True)
            await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Exception: {e}"})
            return False

    async def _get_action_for_current_step(self, current_step_description: str, current_step_index: int):
        logger.info(f"Getting action for step {current_step_index + 1}: {current_step_description}")
        action_json_str: Optional[str] = None
        action_to_execute: Optional[Dict[str, Any]] = None
        self.thinking_process_output = self.thinking_process_output if hasattr(self, 'thinking_process_output') else None # Ensure initialized

        # Check if we need a new screenshot or can reuse the existing one
        need_new_screenshot = False
        
        # Take a new screenshot only if:
        # 1. We don't have a current screenshot
        # 2. The LLM explicitly requested a new screenshot (check step description)
        # 3. This is a retry after a failed operation that might have changed the screen
        # 4. This is not the first step (step index > 0) - always take a new screenshot after first action
        if (not self.current_screenshot_path or 
            any(keyword in current_step_description.lower() for keyword in ['screenshot', 'new image', 'retake', 'capture', 'updated view']) or
            getattr(self, '_screenshot_invalidated', False) or
            current_step_index > 0):  # Always take new screenshot after first action
            need_new_screenshot = True
            
        try:
            if need_new_screenshot:
                logger.info(f"Taking new screenshot for step {current_step_index + 1}")
                await self.manage_gui_window_func("hide")
                await asyncio.sleep(0.5)
                screenshot_filename = f"automoy_step_{current_step_index + 1}_action_context.png"
                self.current_screenshot_path = self.desktop_utils.capture_current_screen(filename_prefix=screenshot_filename.split('.')[0])
                await self.manage_gui_window_func("show")
                await asyncio.sleep(0.5)

                if not self.current_screenshot_path:
                    logger.error("Failed to capture screenshot for action generation.")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": "Failed to capture screenshot."}],
                        "thinking_process": "Error: Screenshot capture failed."
                    })
                    return None
                
                # Send path of the raw screenshot to GUI for it to copy and display
                logger.debug(f"Updating GUI with raw screenshot path for action generation: {str(self.current_screenshot_path)}")
                await self._update_gui_state_func("/state/screenshot", {"path": str(self.current_screenshot_path)}) # MODIFIED (payload key)

                # Perform new visual analysis
                self.current_processed_screenshot_path, self.visual_analysis_output = await self._perform_visual_analysis(
                    screenshot_path=self.current_screenshot_path,
                    task_context=f"Current step: {current_step_description}"
                )
                
                # Reset the screenshot invalidation flag
                self._screenshot_invalidated = False
            else:
                logger.info(f"Reusing existing screenshot and visual analysis for step {current_step_index + 1}")
                # Update GUI with existing screenshot path
                if self.current_screenshot_path:
                    await self._update_gui_state_func("/state/screenshot", {"path": str(self.current_screenshot_path)})
                
            if not self.visual_analysis_output:
                logger.warning("Visual analysis failed or produced no output for the current step. Proceeding with fallback approach.")
                # Set fallback visual analysis info
                self.visual_analysis_output = f"Visual analysis not available for step: {current_step_description}. Proceeding based on step description and objective."
                await self._update_gui_state_func("/state/visual", {"text": self.visual_analysis_output})
                # Don't return here - continue with action generation using fallback approach

        except Exception as e_screenshot_va:
            logger.error(f"Error during screenshot capture or visual analysis for action: {e_screenshot_va}", exc_info=True)
            # Set fallback info and continue
            self.visual_analysis_output = f"Error during visual analysis: {e_screenshot_va}. Proceeding with step description only."
            await self._update_gui_state_func("/state/visual", {"text": self.visual_analysis_output})
            # Don't return here - continue with action generation using fallback approach

        step_retry_count = 0
        while step_retry_count < self.max_retries_per_step:
            await self.pause_event.wait()
            if not self.pause_event.is_set(): # Check if pause_event is not set (meaning pause is active)
                 logger.info("Operation paused by user. Waiting for resume...")
                 await self._update_gui_state_func("/state/operator_status", {"text": "Paused"}) # MODIFIED (payload key)
                 await self.pause_event.wait() # Wait until event is set (resume)
                 logger.info("Operation resumed by user.")
                 await self._update_gui_state_func("/state/operator_status", {"text": f"Resumed. Processing step {current_step_index + 1}"}) # MODIFIED (payload key)

            logger.info(f"Attempt {step_retry_count + 1}/{self.max_retries_per_step} to generate action for step: {current_step_description}")
            
            # Update Current Operation display instead of generic status
            await self._update_gui_state_func("/state/current_operation", {
                "operation": f"Analyzing step {current_step_index + 1}: {current_step_description[:50]}...",
                "step_index": current_step_index + 1,
                "status": "generating_action",
                "attempt": step_retry_count + 1
            })
            
            await self._update_gui_state_func("/state/operator_status", {"text": f"Generating action for step {current_step_index + 1} (Attempt {step_retry_count + 1})"}) # MODIFIED (payload key)

            try:
                system_prompt_action = ACTION_GENERATION_SYSTEM_PROMPT
                
                # Use the new action generation prompt template
                user_prompt_action = ACTION_GENERATION_USER_PROMPT_TEMPLATE.format(
                    step_description=current_step_description,
                    objective=self.objective,
                    visual_analysis=self.visual_analysis_output or "No visual analysis available."
                )

                messages_action = [
                    {"role": "system", "content": system_prompt_action},
                    {"role": "user", "content": user_prompt_action}
                ]
                
                logger.debug(f"Messages for action generation LLM call (first 200 chars of user prompt): {str(messages_action)[:200]}")

                raw_llm_response, thinking_output, llm_error = await self.llm_interface.get_next_action(
                    model=self.config.get_model(),
                    messages=messages_action,
                    objective=self.objective,
                    session_id=self.session_id,
                    screenshot_path=str(self.current_processed_screenshot_path) if self.current_processed_screenshot_path else str(self.current_screenshot_path)
                )
                
                self.thinking_process_output = thinking_output

                if llm_error:
                    logger.error(f"LLM error during action generation: {llm_error}")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": f"LLM Error: {llm_error}"}],
                        "thinking_process": self.thinking_process_output or f"LLM Error: {llm_error}"
                    })
                    step_retry_count += 1
                    if step_retry_count >= self.max_retries_per_step:
                        break
                    await asyncio.sleep(1)
                    continue

                if not raw_llm_response:
                    logger.warning("LLM returned no response for action generation.")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "info", "summary": "LLM provided no action this attempt."}],
                        "thinking_process": self.thinking_process_output or "LLM gave empty response."
                    })
                    step_retry_count += 1
                    if step_retry_count >= self.max_retries_per_step:
                        break
                    await asyncio.sleep(1) 
                    continue
                
                # Log the raw LLM response to debug JSON parsing issues
                logger.info(f"Raw LLM response for action generation: {str(raw_llm_response)[:1000]}...")
                
                action_json_str = handle_llm_response(raw_llm_response, "action_generation", is_json=True, 
                                                    objective=self.objective, 
                                                    current_step_description=current_step_description,
                                                    visual_analysis_output=self.visual_analysis_output)
                # Fix: Ensure action_json_str is properly converted to string before slicing
                action_str_preview = str(action_json_str)[:500] if action_json_str else 'None'
                logger.debug(f"LLM response (action_json_str) for action generation: {action_str_preview}")

                if not action_json_str:
                    logger.warning("handle_llm_response returned None or empty for action_json_str.")
                    
                    # Try desktop fallback immediately for better results
                    if hasattr(self, 'desktop_utils') and self.desktop_utils:
                        fallback_action = self.desktop_utils.generate_desktop_fallback_action(
                            step_description=current_step_description,
                            objective=self.objective
                        )
                        if fallback_action:
                            logger.info(f"Generated desktop fallback action for empty response: {fallback_action}")
                            action_to_execute = fallback_action
                            self.operations_generated_for_gui = [action_to_execute]
                            await self._update_gui_state_func("/state/operations_generated", {
                                "operations": self.operations_generated_for_gui,
                                "thinking_process": "Used desktop fallback due to empty LLM response"
                            })
                            break
                    
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "warning", "summary": "Failed to parse LLM action response."}],
                        "thinking_process": self.thinking_process_output or "Could not parse LLM action."
                    })
                    step_retry_count += 1
                    if step_retry_count >= self.max_retries_per_step:
                        break
                    await asyncio.sleep(1)
                    continue

                # Check if handle_llm_response returned an error dict
                if isinstance(action_json_str, dict) and "error" in action_json_str:
                    logger.error(f"Error from handle_llm_response for action: {action_json_str}")
                    
                    # Try desktop fallback when JSON parsing fails
                    if self.config.get('DESKTOP_ANCHOR_POINT', False):
                        logger.info("JSON parsing failed, trying desktop fallback action generation...")
                        fallback_action = await self._generate_desktop_fallback_action(
                            step_description=current_step_description,
                            objective=self.objective
                        )
                        if fallback_action:
                            logger.info(f"Generated desktop fallback action for JSON error: {fallback_action}")
                            action_to_execute = fallback_action
                            self.operations_generated_for_gui = [action_to_execute]
                            await self._update_gui_state_func("/state/operations_generated", {
                                "operations": self.operations_generated_for_gui,
                                "thinking_process": "Used desktop fallback due to JSON parsing error"
                            })
                            break
                        else:
                            logger.warning("Desktop fallback action generation also failed for JSON error")
                    
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": f"LLM response error: {action_json_str.get('message', 'Unknown error')}"}],
                        "thinking_process": self.thinking_process_output or "LLM response parsing failed."
                    })
                    step_retry_count += 1
                    if step_retry_count >= self.max_retries_per_step:
                        break
                    await asyncio.sleep(1)
                    continue

                try:
                    if isinstance(action_json_str, dict):
                        # handle_llm_response already parsed it
                        parsed_action = action_json_str
                    else:
                        # It's a string, parse it
                        parsed_action = json.loads(action_json_str)
                    
                    # Check for valid action format - support both old and new field names
                    has_action_type = "action_type" in parsed_action or "type" in parsed_action
                    has_description = "description" in parsed_action or "summary" in parsed_action
                    
                    if isinstance(parsed_action, dict) and has_action_type:
                        action_to_execute = parsed_action 
                        
                        # Ensure action has required fields for execution
                        if "action_type" not in action_to_execute and "type" in action_to_execute:
                            action_to_execute["action_type"] = action_to_execute["type"]
                        if "description" not in action_to_execute and "summary" in action_to_execute:
                            action_to_execute["description"] = action_to_execute["summary"]
                        
                        # Ensure click actions have coordinates
                        if action_to_execute.get("action_type") == "click":
                            if not action_to_execute.get("coordinate") and not (action_to_execute.get("x") and action_to_execute.get("y")):
                                logger.warning("Click action missing coordinates, adding fallback coordinates")
                                action_to_execute["coordinate"] = {"x": 300, "y": 200}
                        
                        self.operations_generated_for_gui = [action_to_execute]
                        logger.info(f"✅ Action proposed by LLM: {action_to_execute}")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": self.operations_generated_for_gui,
                            "thinking_process": self.thinking_process_output or "N/A"
                        })
                        break 
                    else:
                        logger.warning(f"Parsed action JSON is not in the expected format. Missing action_type/type field: {parsed_action}")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": [{"type": "error", "summary": "LLM action response has incorrect format."}],
                            "thinking_process": self.thinking_process_output or "Action format error."
                        })
                        
                        # Try desktop fallback when action format is invalid
                        if self.config.get('DESKTOP_ANCHOR_POINT', False):
                            logger.info("Invalid action format, trying desktop fallback action generation...")
                            fallback_action = await self._generate_desktop_fallback_action(
                                step_description=current_step_description,
                                objective=self.objective
                            )
                            if fallback_action:
                                logger.info(f"🔄 Generated desktop fallback action: {fallback_action}")
                                action_to_execute = fallback_action
                                self.operations_generated_for_gui = [action_to_execute]
                                await self._update_gui_state_func("/state/operations_generated", {
                                    "operations": self.operations_generated_for_gui,
                                    "thinking_process": "Used desktop fallback due to invalid action format"
                                })
                                break
                        
                        step_retry_count += 1
                        if step_retry_count >= self.max_retries_per_step:
                            break
                        await asyncio.sleep(1)
                        continue
                except json.JSONDecodeError as jde:
                    logger.error(f"JSONDecodeError parsing action_json_str: {jde}. Content: {action_json_str}")
                    
                    # Try desktop fallback when JSON parsing fails
                    if self.config.get('DESKTOP_ANCHOR_POINT', False):
                        logger.info("JSONDecodeError occurred, trying desktop fallback action generation...")
                        fallback_action = await self._generate_desktop_fallback_action(
                            step_description=current_step_description,
                            objective=self.objective
                        )
                        if fallback_action:
                            logger.info(f"Generated desktop fallback action for JSONDecodeError: {fallback_action}")
                            action_to_execute = fallback_action
                            self.operations_generated_for_gui = [action_to_execute]
                            await self._update_gui_state_func("/state/operations_generated", {
                                "operations": self.operations_generated_for_gui,
                                "thinking_process": "Used desktop fallback due to JSONDecodeError"
                            })
                            break
                        else:
                            logger.warning("Desktop fallback action generation also failed")
                    
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": "Invalid JSON from LLM for action."}],
                        "thinking_process": self.thinking_process_output or f"JSON Error: {jde}"
                    })
                    step_retry_count += 1
                    if step_retry_count >= self.max_retries_per_step:
                        break
                    await asyncio.sleep(1)
                    continue

            except Exception as e_llm_action: # This except block pairs with the outer try for the LLM call attempt
                logger.error(f"Exception during LLM call for action generation (attempt {step_retry_count + 1}): {e_llm_action}", exc_info=True)
                # Fix: Ensure the exception is properly converted to string to avoid slice object errors
                error_msg = str(e_llm_action) if not isinstance(e_llm_action, slice) else f"Slice object error: {repr(e_llm_action)}"
                await self._update_gui_state_func("/state/operations_generated", {
                    "operations": [{"type": "error", "summary": f"Error generating action: {error_msg}"}],
                    "thinking_process": self.thinking_process_output or f"Exception: {error_msg}"
                })
            
            # Always increment retry count and check max retries
            if not action_to_execute:  # Only increment if we didn't successfully get an action
                step_retry_count += 1
                
                # Try desktop fallback earlier - after 2 failed attempts instead of waiting until the end
                if step_retry_count >= 2 and self.config.get('DESKTOP_ANCHOR_POINT', False):
                    logger.info(f"🔄 LLM failed {step_retry_count} times, trying desktop fallback action generation...")
                    fallback_action = await self._generate_desktop_fallback_action(
                        step_description=current_step_description,
                        objective=self.objective
                    )
                    if fallback_action:
                        logger.info(f"✅ Generated desktop fallback action: {fallback_action}")
                        action_to_execute = fallback_action
                        break  # Exit retry loop with fallback action
                    else:
                        logger.warning("Desktop fallback action generation also failed")
                
                if step_retry_count >= self.max_retries_per_step:
                    logger.error(f"❌ Max retries ({self.max_retries_per_step}) reached for generating action for step {current_step_index + 1}.")
                    
                    # Force a basic fallback action as last resort
                    if self.objective and "calculator" in self.objective.lower():
                        action_to_execute = {
                            "action_type": "key_sequence",
                            "keys": "win+s",
                            "description": "Emergency fallback: Open Windows search for Calculator",
                            "confidence": 50
                        }
                        logger.info(f"🚨 Emergency Calculator fallback: {action_to_execute}")
                    elif self.objective and "chrome" in self.objective.lower():
                        action_to_execute = {
                            "action_type": "key_sequence", 
                            "keys": "win+s",
                            "description": "Emergency fallback: Open Windows search for Chrome",
                            "confidence": 50
                        }
                        logger.info(f"🚨 Emergency Chrome fallback: {action_to_execute}")
                    else:
                        action_to_execute = {
                            "action_type": "key",
                            "key": "win",
                            "description": "Emergency fallback: Press Windows key",
                            "confidence": 40
                        }
                        logger.info(f"🚨 Emergency generic fallback: {action_to_execute}")
                    
                    if action_to_execute:
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": [action_to_execute],
                            "thinking_process": f"Emergency fallback after {self.max_retries_per_step} failed attempts"
                        })
                        break
                    else:
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": [{"type": "error", "summary": f"Max retries reached. Could not generate action for: {current_step_description}"}],
                            "thinking_process": self.thinking_process_output or "Max retries for action generation."
                        })
                        # Also update operator status
                        await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Max retries for action on step {current_step_index + 1}"})
                        break  # Exit the retry loop
                
                # Pause before next attempt if we haven't reached max retries
                logger.info(f"Pausing before next action generation retry attempt for step {current_step_index + 1}.")
                await asyncio.sleep(min(5, step_retry_count * 2)) 

        if not action_to_execute:
            logger.error(f"Failed to generate a valid action for step {current_step_index + 1} after all retries.")
            return None

        self.last_proposed_action = action_to_execute
        logger.info(f"Successfully generated action for step {current_step_index + 1}: {action_to_execute}")
        return action_to_execute

    async def operate_loop(self):
        """
        NEW COLLABORATIVE APPROACH:
        Goal → Initial Visual Analysis (ONCE) → Collaborative Thinking & Steps → Execution Loop
        """
        logger.info("🚀 AutomoyOperator.operate_loop started with NEW collaborative approach.")
        await self._update_gui_state_func("/state/operator_status", {"text": "Starting Collaborative Operator..."})
        
        try:
            # PHASE 1: INITIAL VISUAL ANALYSIS (DONE ONCE PER GOAL)
            logger.info("=== PHASE 1: INITIAL VISUAL ANALYSIS (ONCE PER GOAL) ===")
            visual_success = await self._perform_initial_visual_analysis(self.objective)
            
            if not visual_success:
                logger.warning("⚠️ Initial visual analysis failed, but continuing with limited context")
            
            # PHASE 2: COLLABORATIVE THINKING AND STEP GENERATION
            logger.info("=== PHASE 2: COLLABORATIVE THINKING AND STEP GENERATION ===")
            steps_success = await self._collaborative_step_generation(self.objective)
            
            if not steps_success:
                logger.error("❌ Failed to generate steps collaboratively. Trying fallback.")
                # Try the old method as fallback
                steps_success = await self._generate_steps()
                
                if not steps_success:
                    logger.error("❌ Even fallback step generation failed. Cannot proceed.")
                    await self._update_gui_state_func("/state/operator_status", {"text": "Failed: Cannot generate steps"})
                    return
            
            # PHASE 3: EXECUTE STEPS USING SAVED CONTEXT
            logger.info("=== PHASE 3: EXECUTE STEPS USING SAVED VISUAL CONTEXT ===")
            await self._execute_steps_with_saved_context()
            
        except Exception as e:
            logger.error(f"❌ Exception in collaborative operate_loop: {e}", exc_info=True)
            await self._update_gui_state_func("/state/operator_status", {"text": f"Error: {e}"})
        
        logger.info("🏁 AutomoyOperator.operate_loop finished.")

    async def _execute_steps_with_saved_context(self):
        """
        NEW: Execute steps using the saved visual context instead of taking screenshots repeatedly.
        Only take new screenshots when the LLM explicitly requests updated context.
        """
        logger.info(f"🎯 Executing {len(self.steps)} steps with saved visual context")
        
        for step_index, step in enumerate(self.steps):
            if self.stop_event.is_set():
                logger.info("🛑 Stop event set, ending step execution")
                break
                
            await self.pause_event.wait()
            if not self.pause_event.is_set():
                logger.info("⏸️ Operation paused by user. Waiting for resume...")
                await self._update_gui_state_func("/state/operator_status", {"text": "Paused"})
                await self.pause_event.wait()
                logger.info("▶️ Operation resumed by user.")
            
            step_description = step.get("description", "No description")
            logger.info(f"🔄 Processing step {step_index + 1}/{len(self.steps)}: {step_description}")
            
            # Update GUI with current step
            await self._update_gui_state_func("/state/current_operation", {
                "operation": f"Step {step_index + 1}: {step_description}",
                "status": "executing",
                "step_index": step_index + 1,
                "total_steps": len(self.steps)
            })
            
            # Generate action using saved context (no new screenshots unless requested)
            action = await self._get_action_with_saved_context(step_description, step_index)
            
            if not action:
                logger.warning(f"⚠️ No action generated for step {step_index + 1}. Skipping.")
                continue
            
            # Execute the action
            logger.info(f"⚡ Executing action: {action}")
            execution_success = await self._execute_operation(action, step_description)
            
            if execution_success:
                logger.info(f"✅ Step {step_index + 1} completed successfully")
                self.executed_steps.append({
                    "step": step,
                    "action": action,
                    "success": True,
                    "timestamp": time.time()
                })
                
                # Update Past Operation display
                await self._update_gui_state_func("/state/past_operation", {
                    "operation": f"Completed: {step_description}",
                    "action": action.get("description", "No description"),
                    "success": True
                })
                
                # Check if this action might have changed the screen significantly
                if self._action_changes_screen(action):
                    logger.info("🔄 Action might have changed screen, marking context for potential refresh")
                    # Don't automatically take screenshot - let LLM request it if needed
                
            else:
                logger.warning(f"❌ Step {step_index + 1} failed to execute")
                self.executed_steps.append({
                    "step": step,
                    "action": action,
                    "success": False,
                    "timestamp": time.time()
                })
                
                # Update Past Operation display
                await self._update_gui_state_func("/state/past_operation", {
                    "operation": f"Failed: {step_description}",
                    "action": action.get("description", "No description"),
                    "success": False
                })
            
            # Brief pause between steps
            await asyncio.sleep(0.5)
        
        # Final status update
        successful_steps = sum(1 for step in self.executed_steps if step.get("success", False))
        logger.info(f"🎯 Step execution completed: {successful_steps}/{len(self.steps)} successful")
        await self._update_gui_state_func("/state/operator_status", {
            "text": f"Completed: {successful_steps}/{len(self.steps)} steps successful"
        })

    def _action_changes_screen(self, action: Dict[str, Any]) -> bool:
        """
        Determine if an action is likely to change the screen significantly.
        """
        action_type = action.get("action_type", "").lower()
        
        # Actions that typically change the screen
        screen_changing_actions = [
            "click", "key", "key_sequence", "type", 
            "mouse", "enter", "tab", "alt+tab", "win",
            "launch", "open", "start"
        ]
        
        return action_type in screen_changing_actions

    async def _get_action_with_saved_context(self, step_description: str, step_index: int) -> Optional[Dict[str, Any]]:
        """
        NEW: Generate action using saved visual context instead of taking new screenshots.
        The LLM can request updated context if needed.
        """
        logger.info(f"🎯 Generating action for step {step_index + 1} using saved context: {step_description}")
        
        # Update Current Operation display
        await self._update_gui_state_func("/state/current_operation", {
            "operation": f"Analyzing step {step_index + 1}: {step_description[:50]}...",
            "step_index": step_index + 1,
            "status": "generating_action",
            "using_saved_context": True
        })
        
        retry_count = 0
        max_retries = self.max_retries_per_step
        
        while retry_count < max_retries:
            try:
                # Use collaborative action generation with saved context
                system_prompt = """You are an expert at generating UI automation actions.

You have access to saved visual context from when the goal started. If you need updated visual information (like current screen state after actions), you can request it by including a line starting with "SCREENSHOT_REQUEST:" in your response.

Your job is to generate a specific, executable action for the given step.

If you need an updated screenshot, use this format:
SCREENSHOT_REQUEST: [reason why you need updated visual context]

Then provide your action in valid JSON format."""
                
                user_prompt = f"""
                Goal: {self.objective}
                Current Step: {step_description}
                Step Index: {step_index + 1} of {len(self.steps)}
                
                Saved Visual Context (from initial analysis):
                {self.saved_visual_context or 'No visual context available'}
                
                Previous Actions: {len(self.executed_steps)} actions executed
                
                Generate a specific JSON action to execute this step. If you need updated visual context, request it first.
                
                Return ONLY valid JSON with: {{"action_type": "type", "description": "description", ...additional fields as needed}}
                """
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                raw_response, _, error = await self.llm_interface.get_llm_response(
                    model=self.config.get_model(),
                    messages=messages,
                    objective=self.objective,
                    session_id=self.session_id,
                    response_format_type="action_generation"
                )
                
                if error or not raw_response:
                    logger.warning(f"⚠️ LLM error on attempt {retry_count + 1}: {error}")
                    retry_count += 1
                    continue
                
                # Check if LLM requested a screenshot
                if "SCREENSHOT_REQUEST:" in raw_response:
                    lines = raw_response.split('\n')
                    screenshot_reason = None
                    for line in lines:
                        if line.strip().startswith("SCREENSHOT_REQUEST:"):
                            screenshot_reason = line.replace("SCREENSHOT_REQUEST:", "").strip()
                            break
                    
                    if screenshot_reason:
                        logger.info(f"📸 LLM requested updated screenshot: {screenshot_reason}")
                        updated_context = await self._take_requested_screenshot(screenshot_reason, step_index)
                        
                        if updated_context:
                            # Re-run action generation with updated context
                            updated_user_prompt = user_prompt.replace(
                                f"Saved Visual Context (from initial analysis):\n{self.saved_visual_context or 'No visual context available'}",
                                f"Updated Visual Context:\n{updated_context}"
                            )
                            
                            updated_messages = [
                                {"role": "system", "content": system_prompt.replace("If you need updated visual information (like current screen state after actions), you can request it by including a line starting with \"SCREENSHOT_REQUEST:\" in your response.", "You now have updated visual context.")},
                                {"role": "user", "content": updated_user_prompt}
                            ]
                            
                            raw_response, _, error = await self.llm_interface.get_llm_response(
                                model=self.config.get_model(),
                                messages=updated_messages,
                                objective=self.objective,
                                session_id=self.session_id,
                                response_format_type="action_generation_updated"
                            )
                            
                            if error or not raw_response:
                                logger.warning(f"⚠️ LLM error with updated context: {error}")
                                retry_count += 1
                                continue
                
                # Parse the action from the response
                action_json = handle_llm_response(
                    raw_response, 
                    "action_generation", 
                    is_json=True,
                    objective=self.objective,
                    current_step_description=step_description,
                    visual_analysis_output=self.saved_visual_context
                )
                
                if isinstance(action_json, dict) and "error" not in action_json:
                    # Ensure required fields
                    if "action_type" in action_json or "type" in action_json:
                        if "action_type" not in action_json and "type" in action_json:
                            action_json["action_type"] = action_json["type"]
                        if "description" not in action_json and "summary" in action_json:
                            action_json["description"] = action_json["summary"]
                        
                        # Validate click actions have coordinates
                        if action_json.get("action_type") == "click":
                            if not action_json.get("coordinate") and not (action_json.get("x") and action_json.get("y")):
                                logger.warning("⚠️ Click action missing coordinates, adding fallback")
                                action_json["coordinate"] = {"x": 400, "y": 300}
                        
                        logger.info(f"✅ Action generated with saved context: {action_json}")
                        return action_json
                
                logger.warning(f"⚠️ Invalid action format on attempt {retry_count + 1}")
                retry_count += 1
                
            except Exception as e:
                logger.error(f"❌ Exception generating action on attempt {retry_count + 1}: {e}")
                retry_count += 1
            
            await asyncio.sleep(1)
        
        # Fallback to desktop action if all retries failed
        logger.warning(f"⚠️ All attempts failed, using desktop fallback for: {step_description}")
        return await self._generate_desktop_fallback_action(step_description, self.objective)

    async def _take_requested_screenshot(self, reason: str, step_index: int) -> Optional[str]:
        """
        NEW: Take a screenshot only when explicitly requested by the LLM.
        """
        logger.info(f"📸 Taking requested screenshot for step {step_index + 1}: {reason}")
        
        try:
            await self.manage_gui_window_func("hide")
            await asyncio.sleep(0.5)
            
            screenshot_filename = f"automoy_requested_{step_index + 1}_{reason.replace(' ', '_')[:20]}"
            screenshot_path = self.desktop_utils.capture_current_screen(filename_prefix=screenshot_filename)
            
            await self.manage_gui_window_func("show")
            await asyncio.sleep(0.5)
            
            if not screenshot_path:
                logger.error("❌ Failed to capture requested screenshot")
                return None
            
            # Perform visual analysis on the new screenshot
            _, updated_context = await self._perform_visual_analysis(
                screenshot_path=screenshot_path,
                task_context=f"Updated context for step {step_index + 1}: {reason}"
            )
            
            if updated_context:
                logger.info(f"✅ Updated visual context provided: {updated_context[:200]}...")
                # Update GUI with new screenshot
                await self._update_gui_state_func("/state/screenshot", {"path": str(screenshot_path)})
                return updated_context
            else:
                logger.warning("⚠️ Failed to analyze requested screenshot")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception taking requested screenshot: {e}", exc_info=True)
            return None

    async def _generate_objective_thinking(self, current_objective: str) -> bool:
        """PHASE 1: Generate strategic thinking for the current objective"""
        logger.info(f"Generating thinking process for objective: {current_objective}")
        await self._update_gui_state_func("/state/operator_status", {"text": "Generating thinking process..."})
        
        try:
            system_prompt_think = THINKING_PROCESS_SYSTEM_PROMPT
            user_prompt_think = f"""
            Current Objective: {current_objective}
            Original Goal: {getattr(self, 'original_goal', 'N/A')}
            
            Analyze this objective and provide your strategic thinking on how to approach it.
            Consider:
            1. What needs to be done to achieve this objective
            2. What challenges or obstacles might exist
            3. What the expected outcome should be
            4. How this fits into the larger goal
            
            Provide clear, actionable thinking that will guide step generation.
            """
            
            messages_think = [
                {"role": "system", "content": system_prompt_think},
                {"role": "user", "content": user_prompt_think}
            ]
            
            raw_llm_response_think, thinking_output_think, llm_error_think = await self.llm_interface.get_llm_response(
                model=self.config.get_model(),
                messages=messages_think,
                objective=current_objective,
                session_id=self.session_id,
                response_format_type="thinking_process"
            )

            if llm_error_think:
                logger.error(f"LLM error during objective thinking generation: {llm_error_think}")
                self.thinking_process_output = f"Error generating thinking: {llm_error_think}"
                await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                return False
            elif thinking_output_think:
                self.thinking_process_output = thinking_output_think
                logger.info(f"Objective thinking generated: {self.thinking_process_output[:200]}...")
                await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                return True
            elif raw_llm_response_think:
                self.thinking_process_output = raw_llm_response_think
                logger.info(f"Objective thinking (from raw response): {self.thinking_process_output[:200]}...")
                await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                return True
            else:
                logger.warning("LLM returned no thinking output for objective.")
                self.thinking_process_output = "LLM provided no thinking output for this objective."
                await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                return False
                
        except Exception as e:
            logger.error(f"Exception during objective thinking generation: {e}", exc_info=True)
            self.thinking_process_output = f"Exception generating thinking: {e}"
            await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
            return False

    async def _perform_objective_visual_analysis(self, current_objective: str) -> bool:
        """PHASE 2: Perform visual analysis with anchor point consideration"""
        logger.info(f"Performing visual analysis for objective: {current_objective}")
        # Update Current Operation display for visual analysis
        await self._update_gui_state_func("/state/current_operation", {
            "operation": "Analyzing screen state for visual elements",
            "status": "visual_analysis",
            "step": "Taking screenshot and processing"
        })
        
        await self._update_gui_state_func("/state/operator_status", {"text": "Analyzing screen state..."})
        
        try:
            # Check if desktop anchor point is enabled
            desktop_anchor_enabled = self.config.get("DESKTOP_ANCHOR_POINT", False)
            if desktop_anchor_enabled:
                logger.info("Desktop anchor point enabled. Showing desktop before visual analysis.")
                try:
                    DesktopUtils.show_desktop()
                    await asyncio.sleep(1.0)
                    logger.info("Desktop shown successfully as anchor point.")
                except Exception as e:
                    logger.warning(f"Failed to show desktop as anchor point: {e}. Continuing anyway.")
            
            # Capture screenshot for analysis
            await self.manage_gui_window_func("hide")
            await asyncio.sleep(0.5)
            screenshot_path_obj = self.desktop_utils.capture_current_screen(filename_prefix=f"automoy_objective_{current_objective.replace(' ', '_')[:20]}_")
            await self.manage_gui_window_func("show")
            await asyncio.sleep(0.5)
            
            if not screenshot_path_obj:
                logger.error("Failed to capture screenshot for objective visual analysis.")
                await self._update_gui_state_func("/state/visual", {"text": "Error: Failed to capture screenshot for analysis."})
                return False
            
            # Update GUI with screenshot
            await self._update_gui_state_func("/state/screenshot", {"path": str(screenshot_path_obj)})
            
            # Perform visual analysis
            self.current_screenshot_path = screenshot_path_obj
            self.current_processed_screenshot_path, self.visual_analysis_output = await self._perform_visual_analysis(
                screenshot_path=screenshot_path_obj,
                task_context=f"Objective: {current_objective}"
            )
            
            if self.visual_analysis_output:
                logger.info(f"Visual analysis completed for objective: {self.visual_analysis_output[:200]}...")
                return True
            else:
                logger.warning("Visual analysis failed for objective. Setting fallback analysis.")
                self.visual_analysis_output = f"Visual analysis not available for objective: {current_objective}. Proceeding with objective-based approach."
                await self._update_gui_state_func("/state/visual", {"text": self.visual_analysis_output})
                return False
                
        except Exception as e:
            logger.error(f"Exception during objective visual analysis: {e}", exc_info=True)
            self.visual_analysis_output = f"Error during visual analysis: {e}. Proceeding with objective-only approach."
            await self._update_gui_state_func("/state/visual", {"text": self.visual_analysis_output})
            return False

    async def _generate_objective_steps(self, current_objective: str) -> bool:
        """PHASE 3: Generate steps from thinking + visual analysis"""
        logger.info(f"Generating steps for objective: {current_objective}")
        await self._update_gui_state_func("/state/operator_status", {"text": "Generating action steps..."})
        
        try:
            system_prompt_steps = STEP_GENERATION_SYSTEM_PROMPT
            user_prompt_steps = self.llm_interface.construct_step_generation_prompt(
                objective=current_objective,
                visual_analysis_output=self.visual_analysis_output or "Visual analysis not available.",
                thinking_process_output=self.thinking_process_output or "No thinking process available.",
                previous_steps_output="N/A"
            )
            
            # Log the prompts for debugging
            logger.debug(f"Step generation system prompt: {system_prompt_steps[:200]}...")
            logger.debug(f"Step generation user prompt: {user_prompt_steps[:200]}...")
            
            messages_steps = [
                {"role": "system", "content": system_prompt_steps},
                {"role": "user", "content": user_prompt_steps}
            ]

            raw_llm_response, _, llm_error = await self.llm_interface.get_llm_response(
                model=self.config.get_model(),
                messages=messages_steps,
                objective=current_objective,
                session_id=self.session_id,
                response_format_type="step_generation" 
            )

            # Log the raw LLM response for debugging
            logger.info(f"Raw LLM response for step generation (first 500 chars): {str(raw_llm_response)[:500]}...")

            if llm_error:
                logger.error(f"LLM error during objective step generation: {llm_error}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"LLM Error: {llm_error}"})
                return False
            
            if not raw_llm_response:
                logger.warning("LLM returned no response for objective step generation.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM provided no response for steps."})
                return False

            # Enhanced logging before calling handle_llm_response
            logger.info(f"Calling handle_llm_response for step_generation with response length: {len(str(raw_llm_response))}")
            steps_text = handle_llm_response(raw_llm_response, "step_generation", is_json=False)
            logger.info(f"handle_llm_response returned for steps: {type(steps_text)} - {str(steps_text)[:200]}...")

            # Check if steps_text is an error dict
            if isinstance(steps_text, dict) and "error" in steps_text:
                logger.error(f"handle_llm_response returned error: {steps_text}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"LLM response parsing error: {steps_text.get('message', 'Unknown error')}"})
                return False

            if not steps_text:
                logger.warning("handle_llm_response returned None or empty for objective steps.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to parse LLM step response."})
                return False
            
            # Parse the numbered list from plain text
            # Check if steps_text is an error dict
            if isinstance(steps_text, dict) and "error" in steps_text:
                logger.error(f"handle_llm_response returned error: {steps_text}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"LLM response parsing error: {steps_text.get('message', 'Unknown error')}"})
                return False
                for line in steps_lines:
            if not steps_text:e.strip()
                logger.warning("handle_llm_response returned None or empty for objective steps.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to parse LLM step response."})
                return False
                    # Look for numbered steps (1. 2. etc.) or steps with - or * 
            # Parse the numbered list from plain text
            try:    step_match = re.match(r'^(\d+\.|\d+\)|\*|-)\s*(.+)', line)
                # Extract numbered steps from the text
                steps_lines = steps_text.strip().split('\n')2).strip()
                parsed_steps = []eps.append({
                            "description": step_description,
                for line in steps_lines:ion"
                    line = line.strip()
                    if not line:d not any(keyword in line.lower() for keyword in ['objective:', 'steps:', 'based on', 'guidelines:']):
                        continuee lines that look like steps but aren't numbered
                        parsed_steps.append({
                    # Look for numbered steps (1. 2. etc.) or steps with - or * 
                    import retype": "action"
                    step_match = re.match(r'^(\d+\.|\d+\)|\*|-)\s*(.+)', line)
                    if step_match:
                        step_description = step_match.group(2).strip()
                        parsed_steps.append({
                            "description": step_description,ep.get("description", "No description")} for step in self.steps]
                            "type": "action"ly parsed {len(parsed_steps)} steps from text response")
                        })self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
                    elif line and not any(keyword in line.lower() for keyword in ['objective:', 'steps:', 'based on', 'guidelines:']):
                        # Include lines that look like steps but aren't numbered
                        parsed_steps.append({und, try to use the entire response as a single step
                            "description": line.strip(),und in response, using entire text as single step")
                            "type": "action"ion": steps_text.strip(), "type": "action"}]
                        })teps_for_gui = [{"description": steps_text.strip()}]
                    await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
                if parsed_steps:
                    self.steps = parsed_steps
                    self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                    logger.info(f"Successfully parsed {len(parsed_steps)} steps from text response")
                    await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})sing step text: {parse_error}"})
                    return True
                else:
                    # If no numbered steps found, try to use the entire response as a single step
                    logger.warning("No numbered steps found in response, using entire text as single step")
                    self.steps = [{"description": steps_text.strip(), "type": "action"}]rror": f"Error generating steps: {e}"})
                    self.steps_for_gui = [{"description": steps_text.strip()}]
                    await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
                    return Truek_objective_steps(self, current_objective: str) -> bool:
                    basic fallback steps for the objective"""
            except Exception as parse_error:eps for objective: {current_objective}")
                logger.error(f"Error parsing plain text steps: {parse_error}", exc_info=True)
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Error parsing step text: {parse_error}"})
                return False await self._generate_fallback_steps()
            if fallback_steps:
        except Exception as e:allback_steps
            logger.error(f"Error generating objective steps: {e}", exc_info=True) description")} for step in self.steps]
            await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Error generating steps: {e}"})
            return Falself._update_gui_state_func("/state/steps_generated", {
                    "steps": self.steps_for_gui,
    async def _generate_fallback_objective_steps(self, current_objective: str) -> bool:: {current_objective}"
        """Generate basic fallback steps for the objective"""
        logger.info(f"Generating fallback steps for objective: {current_objective}")
            else:
        try:    logger.error("Fallback step generation failed for objective.")
            fallback_steps = await self._generate_fallback_steps()nerated", {"steps": [], "error": "All step generation methods failed for objective."})
            if fallback_steps:
                self.steps = fallback_steps
                self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                logger.info(f"Generated {len(fallback_steps)} fallback steps for objective.")
                await self._update_gui_state_func("/state/steps_generated", {
                    "steps": self.steps_for_gui,rent_objective: str, objective_iteration: int) -> bool:
                    "warning": f"Generated basic steps for objective (limited analysis): {current_objective}"
                })o(f"Executing steps for objective {objective_iteration}: {current_objective}")
                return True
            else:lf.steps:
                logger.error("Fallback step generation failed for objective.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "All step generation methods failed for objective."})
                return False
        except Exception as e:x = 0
            logger.error(f"Exception during fallback objective step generation: {e}", exc_info=True)
            return False
        while self.current_step_index < len(self.steps) and not self.stop_event.is_set():
    async def _execute_objective_steps(self, current_objective: str, objective_iteration: int) -> bool:
        """PHASE 4: Execute the generated steps and create operations"""
        logger.info(f"Executing steps for objective {objective_iteration}: {current_objective}")
            current_step_description = current_step.get("description", "No description")
        if not self.steps:
            logger.error("No steps available to execute for objective.")len(self.steps)} for objective {objective_iteration}: {current_step_description}")
            return False
            # Update GUI with current step
        self.current_step_index = 0state_func("/state/current_step", {
        objective_completed = Falsecurrent_step_index, 
                "description": current_step_description, 
        while self.current_step_index < len(self.steps) and not self.stop_event.is_set():
            await self.pause_event.wait()jective_iteration
            })
            current_step = self.steps[self.current_step_index]_status", {"text": f"Objective {objective_iteration}: Step {self.current_step_index + 1}"})
            current_step_description = current_step.get("description", "No description")
            # Generate and execute operation for this step
            logger.info(f"Executing step {self.current_step_index + 1}/{len(self.steps)} for objective {objective_iteration}: {current_step_description}")
            
            # Update GUI with current step
            await self._update_gui_state_func("/state/current_step", {nt_step_index + 1}: {action_to_execute}")
                "step_index": self.current_step_index, 
                "description": current_step_description, roper operation details
                "total_steps": len(self.steps),to_execute.get("description", "")
                "objective_iteration": objective_iteration
            })      action_type = action_to_execute.get("action_type", action_to_execute.get("type", ""))
            await self._update_gui_state_func("/state/operator_status", {"text": f"Objective {objective_iteration}: Step {self.current_step_index + 1}"})
                        key_name = action_to_execute.get("key", "")
            # Generate and execute operation for this stepey_name} key"
            action_to_execute = await self._get_action_for_current_step(current_step_description, self.current_step_index)
                        operation_description = f"Click at coordinates"
            if action_to_execute:
                logger.info(f"Generated operation for step {self.current_step_index + 1}: {action_to_execute}")
                
                # Update Current Operation display with proper operation details
                operation_description = action_to_execute.get("description", "")
                if not operation_description:t_step_index + 1,
                    action_type = action_to_execute.get("action_type", action_to_execute.get("type", ""))
                    if action_type == "key":
                        key_name = action_to_execute.get("key", "")
                        operation_description = f"Press {key_name} key"
                    elif action_type == "click":E OPERATION: {action_to_execute}")
                        operation_description = f"Click at coordinates"n_to_execute, current_step_description)
                    else:fo(f"🎯 OPERATION EXECUTION RESULT: {execution_success}")
                        operation_description = f"Execute {action_type} operation"
                if execution_success:
                await self._update_gui_state_func("/state/current_operation", {ep_index + 1}")
                    "operation": operation_description,
                    "step_index": self.current_step_index + 1,ight have changed the screen
                    "objective_iteration": objective_iterationtion_type", action_to_execute.get("type", "")).lower()
                })  if operation_type in ["key", "keyboard", "click", "mouse", "key_sequence"]:
                        logger.info("Operation executed that may have changed the screen - invalidating screenshot for next step")
                # Execute the operationt_invalidated = True
                logger.info(f"🚀 ABOUT TO EXECUTE OPERATION: {action_to_execute}")
                execution_success = await self._execute_operation(action_to_execute, current_step_description)
                logger.info(f"🎯 OPERATION EXECUTION RESULT: {execution_success}")
                        "operation": operation_description,
                if execution_success: self.current_step_index + 1,
                    logger.info(f"✅ Successfully executed step {self.current_step_index + 1}")
                        "status": "completed"
                    # Invalidate screenshot if the operation might have changed the screen
                    operation_type = action_to_execute.get("action_type", action_to_execute.get("type", "")).lower()
                    if operation_type in ["key", "keyboard", "click", "mouse", "key_sequence"]:
                        logger.info("Operation executed that may have changed the screen - invalidating screenshot for next step")
                        self._screenshot_invalidated = Truethis step
                    if await self._check_objective_completion(current_objective):
                    # Update Past Operation displayjective_iteration} completed!")
                    await self._update_gui_state_func("/state/past_operation", {
                        "operation": operation_description,
                        "step_index": self.current_step_index + 1,
                        "objective_iteration": objective_iteration,.current_step_index + 1}")
                        "status": "completed"
                    })Update Past Operation display with failure
                    await self._update_gui_state_func("/state/past_operation", {
                    self.current_step_index += 1escription,
                        "step_index": self.current_step_index + 1,
                    # Check if objective is complete after this step
                    if await self._check_objective_completion(current_objective):
                        logger.info(f"Objective {objective_iteration} completed!")
                        objective_completed = Trueep, but this could be improved with retry logic
                        breakent_step_index += 1
                else:
                    logger.warning(f"❌ Failed to execute step {self.current_step_index + 1}") + 1}")
                    .current_step_index += 1
                    # Update Past Operation display with failure
                    await self._update_gui_state_func("/state/past_operation", {
                        "operation": operation_description,
                        "step_index": self.current_step_index + 1,step_description: str) -> bool:
                        "objective_iteration": objective_iteration,
                        "status": "failed" {operation} for step: {step_description}")
                    })
                    # For now, continue to next step, but this could be improved with retry logic
                    self.current_step_index += 1_type', '')}-{operation.get('key', '')}-{operation.get('description', '')}"
            else:r(self, '_last_executed_operation') and self._last_executed_operation == operation_key:
                logger.error(f"Failed to generate operation for step {self.current_step_index + 1}")
                self.current_step_index += 1
        
        return objective_completed
            # Support both "type" and "action_type" field names
    async def _execute_operation(self, operation: Dict[str, Any], step_description: str) -> bool:
        """Execute a single operation with actual implementation"""
        logger.info(f"Executing operation: {operation} for step: {step_description}")
                # Handle keyboard operations
        # Check if this is a duplicate operation to prevent multiple executions
        operation_key = f"{operation.get('action_type', '')}-{operation.get('key', '')}-{operation.get('description', '')}"
        if hasattr(self, '_last_executed_operation') and self._last_executed_operation == operation_key:
            logger.warning(f"Preventing duplicate operation execution: {operation_key}")")
            return Truef.os_interface.press("win")
                    await asyncio.sleep(0.8)  # Wait for Start menu to open
        try:        logger.info("✅ Windows key press COMPLETED - Start menu should now be visible")
            # Support both "type" and "action_type" field namesey
            operation_type = operation.get("type", operation.get("action_type", "")).lower()
                    
            if operation_type == "key" or operation_type == "keyboard":
                # Handle keyboard operationstrl+Esc keyboard shortcut")
                key_to_press = operation.get("key", "").lower()
                    await asyncio.sleep(0.5)  # Wait for Start menu to open
                if key_to_press == "win" or key_to_press == "windows":
                    logger.info("🔥 EXECUTING WINDOWS KEY PRESS - Should open Start menu")
                    self.os_interface.press("win")
                    await asyncio.sleep(0.8)  # Wait for Start menu to open
                    logger.info("✅ Windows key press COMPLETED - Start menu should now be visible")
                    self._last_executed_operation = operation_keyess}")
                    return Trueerface.press(key_to_press)
                    await asyncio.sleep(0.2)
                elif key_to_press == "ctrl+esc":n = operation_key
                    logger.info("Executing Ctrl+Esc keyboard shortcut")
                    self.os_interface.hotkey("ctrl", "esc")
                    await asyncio.sleep(0.5)  # Wait for Start menu to open
                    logger.info("Ctrl+Esc shortcut completed")")
                    self._last_executed_operation = operation_key
                    return True
                    logger.info(f"Executing key sequence: {keys}")
                else:ey_parts = keys.split("+")
                    logger.info(f"Executing key press: {key_to_press}")
                    self.os_interface.press(key_to_press)ts)
                    await asyncio.sleep(0.2)
                    self._last_executed_operation = operation_key
                    return Trueio.sleep(0.5)
                    self._last_executed_operation = operation_key
            elif operation_type == "key_sequence":
                # Handle key sequences (e.g., "win+s", "ctrl+c")
                keys = operation.get("keys", "")eration_type == "mouse":
                if keys: mouse click operations with improved coordinate parsing
                    logger.info(f"Executing key sequence: {keys}")
                    key_parts = keys.split("+")
                    if len(key_parts) > 1:
                        self.os_interface.hotkey(*key_parts)
                    else:inate" in operation:
                        self.os_interface.press(keys)
                    await asyncio.sleep(0.5)t):
                    self._last_executed_operation = operation_key
                    return Truerd.get("y")
                    elif isinstance(coord, list) and len(coord) >= 2:
            elif operation_type == "click" or operation_type == "mouse":
                # Handle mouse click operations with improved coordinate parsing
                x = None
                y = Noneck to direct x, y fields
                if x is None:
                # Try multiple ways to get coordinates
                if "coordinate" in operation:
                    coord = operation["coordinate"]
                    if isinstance(coord, dict):
                        x = coord.get("x")not None:
                        y = coord.get("y")
                    elif isinstance(coord, list) and len(coord) >= 2:
                        x = coord[0]
                        y = coord[1]f"🖱️ Executing mouse click at ({x}, {y})")
                        self.os_interface.move_mouse(x, y)
                # Fallback to direct x, y fields)  # Slightly longer wait for movement
                if x is None:os_interface.click_mouse()
                    x = operation.get("x")p(0.3)   # Longer wait after click for UI response
                if y is None:r.info(f"✅ Mouse click completed at ({x}, {y})")
                    y = operation.get("y")d_operation = operation_key
                        return True
                if x is not None and y is not None:as e:
                    try:logger.error(f"Invalid coordinates for click: x={x}, y={y}, error: {e}")
                        x = int(x)se
                        y = int(y)
                        logger.info(f"🖱️ Executing mouse click at ({x}, {y})")s. Operation: {operation}")
                        self.os_interface.move_mouse(x, y)
                        await asyncio.sleep(0.15)  # Slightly longer wait for movement
                        self.os_interface.click_mouse()type == "text":
                        await asyncio.sleep(0.3)   # Longer wait after click for UI response
                        logger.info(f"✅ Mouse click completed at ({x}, {y})")
                        self._last_executed_operation = operation_key
                        return Trueyping text: {text_to_type}")
                    except (ValueError, TypeError) as e:type)
                        logger.error(f"Invalid coordinates for click: x={x}, y={y}, error: {e}")
                        return False
                else:
                    logger.warning(f"❌ Click operation missing valid coordinates. Operation: {operation}")
                    return False
                    
            elif operation_type == "type" or operation_type == "text":
                # Handle text typing operations
                text_to_type = operation.get("text", "")down")
                if text_to_type:on.get("amount", 3)
                    logger.info(f"Typing text: {text_to_type}")")
                    self.os_interface.type_text(text_to_type)
                    await asyncio.sleep(0.2)
                    return True amount if direction == "up" else -amount
                else:ogui.scroll(scroll_amount)
                    logger.warning("Type operation missing text")
                    return False
                    
            elif operation_type == "scroll":
                # Handle scroll operationsperation type: {operation_type}")
                direction = operation.get("direction", "down") success to continue
                amount = operation.get("amount", 3)
                logger.info(f"Scrolling {direction} by {amount}")
                # pyautogui.scroll can be used here
                import pyautogui
                scroll_amount = amount if direction == "up" else -amountexc_info=True)
                pyautogui.scroll(scroll_amount)
                await asyncio.sleep(0.2)
                return Trueompletion(self) -> bool:
                 if the overall goal has been completed"""
            else:fo("Checking goal completion status...")
                logger.warning(f"Unknown operation type: {operation_type}")
                # For unknown operations, just wait and return success to continue
                await asyncio.sleep(0.5)
                return Truerrent state
                pare against the original goal
        except Exception as e:goal has been achieved
            logger.error(f"Error executing operation {operation}: {e}", exc_info=True)
            return Falsen False to continue operation
        return False
    async def _check_goal_completion(self) -> bool:
        """Check if the overall goal has been completed"""jective: str) -> bool:
        logger.info("Checking goal completion status...")ted"""
        logger.info(f"Checking completion status for objective: {current_objective}")
        # Placeholder - in a real implementation, this would:
        # 1. Take a screenshoteal implementation, this would:
        # 2. Analyze the current stateate
        # 3. Compare against the original goalments
        # 4. Determine if the goal has been achieved
        
        # For now, return False to continue operations
        return False

    async def _check_objective_completion(self, current_objective: str) -> bool:completed: bool) -> Optional[str]:
        """Check if the current objective has been completed"""and goal progress"""
        logger.info(f"Checking completion status for objective: {current_objective}")eted: {objective_completed}")
        
        # Placeholder - in a real implementation, this would:
        # 1. Analyze current screen stateng LLM based on current state
        # 2. Compare against objective requirementst that determines the next objective needed to achieve a goal."
        # 3. Determine if objective is complete
            Original Goal: {getattr(self, 'original_goal', self.objective)}
        # For now, return False to continue with steps
        return Falsee Completed: {objective_completed}
            Current Screen State: {self.visual_analysis_output or 'Not available'}
    async def _determine_next_objective(self, current_objective: str, objective_completed: bool) -> Optional[str]:
        """Determine the next objective based on current state and goal progress""".
        logger.info(f"Determining next objective. Current: {current_objective}, Completed: {objective_completed}")
            If no new objective is needed, respond with "NO_NEW_OBJECTIVE".
        try:Otherwise, provide a clear, specific next objective.
            # Generate next objective using LLM based on current state
            system_prompt = "You are an AI assistant that determines the next objective needed to achieve a goal."
            user_prompt = f"""
            Original Goal: {getattr(self, 'original_goal', self.objective)}
            Current Objective: {current_objective}
            Objective Completed: {objective_completed}rompt},
            Current Screen State: {self.visual_analysis_output or 'Not available'}
            ]
            Based on the goal progress, determine what the next objective should be.
            If the goal is complete, respond with "GOAL_COMPLETE".get_llm_response(
            If no new objective is needed, respond with "NO_NEW_OBJECTIVE".
            Otherwise, provide a clear, specific next objective.
                objective=current_objective,
            Response should be a single line with just the next objective or status.
            """ response_format_type="text"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}objective: {llm_error}")
            ]   return None
            
            raw_response, _, llm_error = await self.llm_interface.get_llm_response(
                model=self.config.get_model(),
                messages=messages,"GOAL_COMPLETE", "NO_NEW_OBJECTIVE"]:
                objective=current_objective, determination: {next_objective}")
                session_id=self.session_id,
                response_format_type="text"
            )ogger.info(f"Next objective determined: {next_objective}")
            return next_objective
            if llm_error or not raw_response:
                logger.error(f"Failed to determine next objective: {llm_error}")
                return NoneException determining next objective: {e}", exc_info=True)
            return None
            next_objective = raw_response.strip()
            f _generate_desktop_fallback_action(self, step_description: str, objective: str) -> Optional[Dict[str, Any]]:
            if next_objective in ["GOAL_COMPLETE", "NO_NEW_OBJECTIVE"]:al analysis fails."""
                logger.info(f"Next objective determination: {next_objective}")scription}")
                return None
            _lower = step_description.lower()
            logger.info(f"Next objective determined: {next_objective}")
            return next_objective
            hanced search patterns - try to open search first for most tasks
        except Exception as e:_lower for keyword in ['search', 'find', 'locate', 'look for']):
            logger.error(f"Exception determining next objective: {e}", exc_info=True)]):
            return None{
                    "action_type": "key_sequence",
    async def _generate_desktop_fallback_action(self, step_description: str, objective: str) -> Optional[Dict[str, Any]]:
        """Generate fallback actions for common desktop tasks when visual analysis fails."""
        logger.info(f"🔄 Generating desktop fallback action for step: {step_description}")
                    "confidence": 95
        step_lower = step_description.lower()
        objective_lower = objective.lower()
        # Start menu / Windows key actions
        # Enhanced search patterns - try to open search first for most taskskey', 'win key', 'open start', 'access start']):
        if any(keyword in step_lower for keyword in ['search', 'find', 'locate', 'look for']):
            if not any(keyword in step_lower for keyword in ['type', 'enter', 'press']):
                return {win",
                    "action_type": "key_sequence",to open Start menu",
                    "keys": "win+s",
                    "description": "Open Windows search to find application",
                    "coordinate": None,
                    "confidence": 95
                }tion-specific fallbacks
        if any(keyword in objective_lower for keyword in ['chrome', 'google chrome', 'browser']):
        # Start menu / Windows key actionsor keyword in ['type', 'enter text', 'input']):
        if any(keyword in step_lower for keyword in ['start menu', 'windows key', 'win key', 'open start', 'access start']):
            return {"action_type": "type",
                "action_type": "key",hrome",
                "key": "win",ion": "Type 'Google Chrome' in search box",
                "description": "Press Windows key to open Start menu",
                "coordinate": None,0
                "confidence": 90
            }lif any(keyword in step_lower for keyword in ['click', 'select', 'open']):
                return {
        # Application-specific fallbacksk",
        if any(keyword in objective_lower for keyword in ['chrome', 'google chrome', 'browser']):
            if any(keyword in step_lower for keyword in ['type', 'enter text', 'input']):
                return {fidence": 80
                    "action_type": "type",
                    "text": "Google Chrome",
                    "description": "Type 'Google Chrome' in search box",
                    "coordinate": None,
                    "confidence": 90key_sequence", 
                }   "keys": "win+s",
            elif any(keyword in step_lower for keyword in ['click', 'select', 'open']):
                return {rdinate": None,
                    "action_type": "click",
                    "coordinate": {"x": 400, "y": 300},  # Better center coordinates
                    "description": "Click on Google Chrome application",
                    "confidence": 80e_lower for keyword in ['calculator', 'calc']):
                }y(keyword in step_lower for keyword in ['type', 'enter text', 'input']):
            else:eturn {
                # Default Chrome action - open search
                return {t": "Calculator",
                    "action_type": "key_sequence", r' in search box",
                    "keys": "win+s",ne,
                    "description": "Open Windows search for Chrome",
                    "coordinate": None,
                    "confidence": 85_lower for keyword in ['click', 'select', 'open']):
                }eturn {
                    "action_type": "click",
        elif any(keyword in objective_lower for keyword in ['calculator', 'calc']):s  
            if any(keyword in step_lower for keyword in ['type', 'enter text', 'input']):
                return {fidence": 80
                    "action_type": "type",
                    "text": "Calculator",
                    "description": "Type 'Calculator' in search box",
                    "coordinate": None,
                    "confidence": 90key_sequence",
                }   "keys": "win+s", 
            elif any(keyword in step_lower for keyword in ['click', 'select', 'open']):
                return {rdinate": None,
                    "action_type": "click",
                    "coordinate": {"x": 400, "y": 300},  # Better center coordinates  
                    "description": "Click on Calculator application",
                    "confidence": 80
                }yword in step_lower for keyword in ['press enter', 'hit enter', 'enter key', 'launch']):
            else:n {
                # Default Calculator action - open search
                return {enter",
                    "action_type": "key_sequence", execute/launch",
                    "keys": "win+s", 
                    "description": "Open Windows search for Calculator",
                    "coordinate": None,
                    "confidence": 85
                }yword in step_lower for keyword in ['press escape', 'esc key', 'cancel']):
            return {
        # Generic keyboard actionsy",
        if any(keyword in step_lower for keyword in ['press enter', 'hit enter', 'enter key', 'launch']):
            return {cription": "Press Escape key",
                "action_type": "key",
                "confidence": 95
            }
        
        # Desktop/window management
        if any(keyword in step_lower for keyword in ['minimize', 'hide windows', 'show desktop']):
            return {
                "action_type": "key_sequence",
                "keys": "win+d",
                "description": "Press Win+D to show desktop",
                "coordinate": None,
                "confidence": 90
            }
        
        # Generic click actions
        if any(keyword in step_lower for keyword in ['click', 'tap', 'select']):
            if any(keyword in step_lower for keyword in ['center', 'middle', 'screen']):
                coordinate = {"x": 960, "y": 540}  # Center of 1920x1080 screen
            elif any(keyword in step_lower for keyword in ['taskbar', 'bottom']):
                coordinate = {"x": 960, "y": 1040}  # Taskbar area
            elif any(keyword in step_lower for keyword in ['top', 'menu']):
                coordinate = {"x": 960, "y": 100}   # Top menu area
            else:
                coordinate = {"x": 400, "y": 300}   # Default safe click area
                
            return {
                "action_type": "click",
                "coordinate": coordinate,
                "description": f"Click at coordinates {coordinate}",
                "confidence": 70
            }
        
        # Final fallback - if nothing else matches, try opening search
        logger.warning(f"⚠️ No specific fallback found, using generic Windows search fallback")
        return {
            "action_type": "key_sequence",
            "keys": "win+s",
            "description": "Generic fallback: Open Windows search",
            "coordinate": None,
            "confidence": 60
        }

    def _verify_chrome_running(self) -> bool:
        """
        Verify if Google Chrome is currently running.
        Returns True if Chrome is running, False otherwise.
        """
        try:
            chrome_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                        chrome_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if chrome_processes:
                logger.info(f"Chrome is running - found {len(chrome_processes)} Chrome processes")
                return True
            else:
                logger.info("Chrome is not running - no Chrome processes found")
                return False
        except Exception as e:
            logger.error(f"Error checking Chrome status: {e}")
            return False

    def _verify_operation_success(self, operation_data: Dict[str, Any]) -> bool:
        """
        Verify if an operation was successful based on its intended outcome.
        Returns True if verification indicates success, False otherwise.
        """
        try:
            # For Chrome-related operations, check if Chrome is actually running
            if "chrome" in str(operation_data).lower() or "browser" in str(operation_data).lower():
                time.sleep(2)  # Give Chrome time to start
                return self._verify_chrome_running()
            
            # For other operations, we could add different verification methods
            # For now, assume success if no exception was thrown during execution
            return True
        except Exception as e:
            logger.error(f"Error verifying operation success: {e}")
            return False


