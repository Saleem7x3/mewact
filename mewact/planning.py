
import re
import difflib
from typing import List, Dict, Optional, Tuple
from colorama import Fore

from .config import print, DEBUG_OCR
from .memory import VAR_STORE

# --- 3. COGNITIVE PLANNER (ID SELECTOR) ---
class CognitivePlanner:
    def __init__(self, library_manager):
        from ollama import Client
        self.client = Client(host='http://localhost:11434')
        self.library = library_manager 

    def _extract_json(self, text: str) -> str:
        try:
            match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
            if match: return match.group(1)
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end != -1: return text[start:end+1]
            return text
        except: return text

    def _find_target_coords(self, goal: str, ui_data: List[Dict]) -> Optional[Tuple[int, int]]:
        goal_lower = goal.lower()
        if not any(x in goal_lower for x in ["click", "double", "right"]): return None
        target = goal_lower.replace("double click", "").replace("right click", "").replace("click", "").replace(" on ", "").strip()
        target = target.replace("[", "").replace("]", "")
        if not target: return None
        best_match, best_ratio = None, 0.0
        for item in ui_data:
            ui_text = item['text'].lower()
            if target == ui_text: return (item['x'], item['y'])
            ratio = difflib.SequenceMatcher(None, target, ui_text).ratio()
            if ratio > 0.8 and ratio > best_ratio:
                best_ratio = ratio; best_match = (item['x'], item['y'])
        return best_match

    def plan(self, goal: str, ui_data: List[Dict]) -> Tuple[str, bool]:
        goal_clean = goal.strip()
        
        # --- PARSE INLINE VARIABLE ---
        # Format: "command | variable content" OR "command $V1"
        inline_var = ""
        
        # 1. Standard Pipe Separator
        if "|" in goal_clean:
            parts = goal_clean.split("|", 1)
            goal_clean = parts[0].strip()
            inline_var = parts[1].strip()
            
            # Handle Quoted Variables (ignore garbage after quote)
            # Example: type | "hello" garbage -> var="hello"
            if inline_var.startswith('"') and '"' in inline_var[1:]:
                 end_quote = inline_var.find('"', 1)
                 inline_var = inline_var[1:end_quote]
                 if DEBUG_OCR: print(f"{Fore.YELLOW}[*] Extracted quoted var: '{inline_var}'")
        
        # 2. Handle common typo " I " instead of " | " (OCR error)
        elif " I " in goal_clean:
             # Heuristic: If it looks like "type I text", treat I as separator
             if goal_clean.lower().startswith(("type", "write", "search")):
                 parts = goal_clean.split(" I ", 1)
                 goal_clean = parts[0].strip()
                 inline_var = parts[1].strip()
                 print(f"{Fore.YELLOW}[*] Auto-Corrected 'I' to '|' separator")

        # Resolve any $V references in the variable
        inline_var = VAR_STORE.resolve(inline_var)
        
        # Also resolve $V references in the goal itself (e.g., "type $V1")
        var_ref_match = re.search(r'\$V(\d+)', goal_clean)
        if var_ref_match:
            inline_var = VAR_STORE.get(var_ref_match.group(1))
            goal_clean = re.sub(r'\$V\d+', '', goal_clean).strip()

        # --- LAYER 1: REFLEXES ---
        if goal_clean.lower().startswith(("cmd", "powershell", "echo")):
            print(f"{Fore.CYAN}[*] Reflex: Shell")
            # Escape quotes and backslashes for safe shell execution
            safe_goal = goal_clean.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            return f"subprocess.Popen('{safe_goal}', shell=True)", False

        # --- LAYER 2: SMART KEYWORD FILTER ---
        print(f"{Fore.MAGENTA}    [*] Smart Filter: Matching keywords...")
        
        cmds = self.library.library["commands"]
        if not cmds:
            print(f"{Fore.RED}    [!] Library empty.")
            return "", False

        # 1. Extract keywords from goal
        goal_words = set(goal_clean.lower().split())
        # Remove common stopwords
        stopwords = {'a', 'an', 'the', 'to', 'for', 'on', 'in', 'with', 'and', 'or', 'is', 'it', 'my', 'me', 'i'}
        goal_keywords = goal_words - stopwords
        
        # 2. Find commands matching keywords
        def match_score(cmd_name: str) -> int:
            """Higher score = better match"""
            cmd_words = set(cmd_name.lower().split())
            return len(goal_keywords & cmd_words)
        
        matched_cmds = {}
        for key, data in cmds.items():
            if not isinstance(data, dict): continue
            cid = data.get("id")
            if cid is None: continue
            
            score = match_score(key)
            if score > 0:
                matched_cmds[cid] = {"name": key, "score": score, "code": data["code"], "id": cid, "type": data.get("type", "python")}

        if not matched_cmds:
            print(f"{Fore.RED}    [!] No keyword matches found.")
            return "", False

        # 3. Sort by score
        sorted_cmds = sorted(matched_cmds.values(), key=lambda x: x['score'], reverse=True)
        top_match = sorted_cmds[0]
        
        print(f"{Fore.GREEN}    [+] Matched: '{top_match['name']}' (ID: {top_match['id']})")
        
        code = top_match['code']
        code = code.replace("__VAR__", inline_var)
        
        # --- LAYER 3: VISUAL CONFIRMATION ---
        # If command implies clicking, verify target is visible
        if "click" in top_match['name']:
            target_coords = self._find_target_coords(top_match['name'], ui_data)
            if target_coords:
                 # Inject coordinates into code if it uses a generic click or visual click placeholder
                 print(f"{Fore.YELLOW}    [*] Visual Assist: Found '{top_match['name']}' at {target_coords}")
                 # You could update the code here to click generic coordinates if needed
                 # But for now we proceed with library code (which might use visual aim separately or hardcoded)
            else:
                 pass # Can't visually confirm, hope generic click works or it's a hotkey

        return code, False

    def plan_goal(self, goal: str) -> List[Dict]:
        """
        [AUTONOMY] Generate a multi-step plan for a high-level goal.
        1. Context: Get Screen Description (The Eye)
        2. Recall: Get Relevant Vectors (The Brain)
        3. Reason: Use LLM to generate plan
        """
        import mewact.config as config
        from colorama import Fore
        
        print(f"{Fore.CYAN}[*] Autonomy Engine: Analyzing goal '{goal}'...")
        
        # 1. The Eye (Active Vision)
        screen_context = "Unknown"
        if config.ACTIVE_MODE:
            try:
                from .active_vision import ActiveVisionEngine
                vision = ActiveVisionEngine()
                print(f"{Fore.CYAN}    [*] Scannning screen...")
                screen_context = vision.describe_screen()
                print(f"{Fore.GREEN}    [+] Screen Context: {screen_context[:50]}...")
            except Exception as e:
                print(f"{Fore.RED}    [!] Vision Error: {e}")
        
        # 2. The Brain (Memory)
        memory_context = []
        if self.memory:
            relevant = self.memory.search(goal, k=3)
            for item in relevant:
                cmd_id = item['metadata'].get('id')
                desc = item['text']
                memory_context.append(f"ID {cmd_id}: {desc}")
            if memory_context:
                print(f"{Fore.GREEN}    [+] Recalled {len(memory_context)} relevant skills.")

        # 3. The Reasoner (LLM)
        try:
            import ollama
            
            # Construct Prompt
            prompt = f"""
            GOAL: {goal}
            
            CURRENT SCREEN STATE:
            {screen_context}
            
            RELEVANT SKILLS (MEMORY):
            {chr(10).join(memory_context)}
            
            AVAILABLE TOOLS:
            - type(text): Type text
            - press(key): Press key (e.g. enter, win, ctrl+c)
            - click(text): Click text on screen
            - execute(id): Execute command ID from memory
            - run_python(code): Run python code
            
            TASK:
            Generate a JSON sequence of actions to achieve the GOAL.
            Format: [{{"action": "function_name", "args": ["arg1"]}}, ...]
            
            Keep it simple. Use 'execute(id)' if a relevant skill ID matches perfectly.
            Output ONLY valid JSON.
            """
            
            print(f"{Fore.CYAN}    [*] Generating Plan (Model: {config.PLANNER_MODEL})...")
            response = ollama.chat(model=config.PLANNER_MODEL, messages=[{'role': 'user', 'content': prompt}])
            content = response['message']['content']
            
            # Extract JSON
            json_str = self._extract_json(content)
            import json
            plan = json.loads(json_str)
            
            print(f"{Fore.GREEN}    [+] Plan Generated: {len(plan)} steps.")
            return plan
            
        except Exception as e:
            print(f"{Fore.RED}[!] Planning Error: {e}")
            return []

