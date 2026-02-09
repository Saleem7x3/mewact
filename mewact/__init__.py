
from .config import check_deps, MCP_MODE
from .perception import PerceptionEngine, WindowCapture
from .active_vision import ActiveVisionEngine # Optional import
from .memory import LibraryManager, VariableStore
from .execution import ActionExecutor
from .mobile import MobileController # Optional


from .planning import CognitivePlanner
from .session import SessionManager
from .sentinel import PassiveSentinel
from .main import main
