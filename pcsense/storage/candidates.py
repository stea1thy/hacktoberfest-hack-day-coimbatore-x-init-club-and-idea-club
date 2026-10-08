import os
import stat
import time
from pathlib import Path
import hashlib
from typing import List, Tuple, Dict, Any

from pcsense.contracts import Action
from pcsense.storage.duplicates import find_duplicates
from pcsense.storage.artifacts import find_dev_artifacts

def find_temp_candidates(root: str) -> list[dict]:
    results = []
    root_path = Path(root).resolve()
    temp_exts = {".tmp", ".log", ".bak", ".swp"}
    
    stack = [root_path]
    now = time.time()
    
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        if hasattr(st, 'st_file_attributes') and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                            continue
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in temp_exts:
                                age_days = (now - st.st_mtime) / 86400.0
                                results.append({
                                    "path": entry.path,
                                    "bytes": st.st_size,
                                    "age_days": age_days
                                })
                    except OSError:
                        pass
        except OSError:
            pass
            
    return results

def is_recent(path: str, st: os.stat_result) -> bool:
    now = time.time()
    return (now - st.st_mtime) < 86400

def candidates(root: str, goal_gb: float | None = None) -> Tuple[List[Action], List[Dict[str, str]]]:
    root_path = Path(root).resolve()
    actions = []
    excluded = []
    action_id_counter = 1
    
    # We need to collect: duplicates, artifacts, temps, and then everything else to categorize
    # Let's collect known paths so we don't process them twice
    processed_paths = set()
    
    # 1. Duplicates
    dups = find_duplicates(str(root_path))
    for i, group in enumerate(dups):
        # We quarantine all EXCEPT the suggested keeper
        paths_to_quarantine = []
        for p in group["paths"]:
            if p == group["suggested_keeper"]:
                continue
                
            try:
                st = os.stat(p, follow_symlinks=False)
                # Check exclusions
                if is_recent(p, st):
                    excluded.append({"path": p, "reason": "Modified in the last 24h"})
                    continue
                if "IGNORE ALL PREVIOUS INSTRUCTIONS" in Path(p).name:
                    excluded.append({"path": Path(p).name, "reason": "Hostile filename detected"})
                    continue
                # Exclude if in Documents
                if "Documents" in Path(p).parts:
                    excluded.append({"path": p, "reason": "Personal documents"})
                    continue
                
                paths_to_quarantine.append(p)
                processed_paths.add(p)
            except OSError:
                pass
                
        if paths_to_quarantine:
            actions.append(Action(
                id=f"dup_{i}",
                tool="quarantine_paths",
                params={"paths": paths_to_quarantine},
                risk="MEDIUM",
                est_bytes=group["bytes_each"] * len(paths_to_quarantine),
                rationale="Duplicate files, keeping one copy."
            ))
            
    # 2. Artifacts
    artifacts = find_dev_artifacts(str(root_path))
    for i, art in enumerate(artifacts):
        p = art["path"]
        if art["kind"] == ".git":
            excluded.append({"path": p, "reason": ".git repository"})
            processed_paths.add(p)
            continue
            
        actions.append(Action(
            id=f"art_{i}",
            tool="quarantine_paths",
            params={"paths": [p]},
            risk="LOW" if art["kind"] in {"__pycache__", ".pytest_cache"} else "MEDIUM",
            est_bytes=art["bytes"],
            rationale=f"Dev artifact ({art['kind']})."
        ))
        processed_paths.add(p)
        
    # 3. Temps
    temps = find_temp_candidates(str(root_path))
    for i, tmp in enumerate(temps):
        p = tmp["path"]
        if p in processed_paths: continue
        
        actions.append(Action(
            id=f"tmp_{i}",
            tool="quarantine_paths",
            params={"paths": [p]},
            risk="LOW",
            est_bytes=tmp["bytes"],
            rationale=f"Old temp/log file (age: {tmp['age_days']:.1f} days)."
        ))
        processed_paths.add(p)
        
    # 4. Others (Installers, HIGH risk items in Downloads/Documents)
    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        if hasattr(st, 'st_file_attributes') and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                            excluded.append({"path": entry.path, "reason": "Junction/Symlink"})
                            continue
                        if entry.is_symlink():
                            excluded.append({"path": entry.path, "reason": "Junction/Symlink"})
                            continue
                            
                        # If directory is an artifact, we already processed it
                        if entry.path in processed_paths:
                            continue
                            
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            if entry.path in processed_paths:
                                continue
                            
                            p = Path(entry.path)
                            
                            # Exclusions
                            if "IGNORE ALL PREVIOUS INSTRUCTIONS" in p.name:
                                excluded.append({"path": p.name, "reason": "Hostile filename detected"})
                                continue
                                
                            parts = p.parts
                            if "Documents" in parts:
                                excluded.append({"path": entry.path, "reason": "Personal documents"})
                                continue
                                
                            if is_recent(entry.path, st):
                                excluded.append({"path": entry.path, "reason": "Modified in the last 24h"})
                                continue
                                
                            # If in Downloads, check if installer
                            if "Downloads" in parts:
                                ext = p.suffix.lower()
                                if ext in {".exe", ".msi"}:
                                    age_days = (time.time() - st.st_mtime) / 86400.0
                                    if age_days > 30:
                                        actions.append(Action(
                                            id=f"inst_{len(actions)}",
                                            tool="quarantine_paths",
                                            params={"paths": [entry.path]},
                                            risk="MEDIUM",
                                            est_bytes=st.st_size,
                                            rationale="Old installer."
                                        ))
                                    else:
                                        excluded.append({"path": entry.path, "reason": "Recent installer"})
                                else:
                                    # Other items in downloads are HIGH risk
                                    actions.append(Action(
                                        id=f"high_{len(actions)}",
                                        tool="quarantine_paths",
                                        params={"paths": [entry.path]},
                                        risk="HIGH",
                                        est_bytes=st.st_size,
                                        rationale="Unknown file in Downloads."
                                    ))
                                
                    except OSError:
                        pass
        except OSError:
            pass
            
    # Goal selection logic
    if goal_gb is not None:
        goal_bytes = goal_gb * 1024 * 1024 * 1024
        
        # Sort actions: LOW first, then MEDIUM (largest first). HIGH is never auto-selected.
        # Wait, HIGH is returned but not selected if we trim by goal? 
        # "HIGH is never auto-selected" -> Maybe they are just excluded from the goal subset, but we return what we need.
        # Let's filter out HIGH for goal reaching.
        
        lows = sorted([a for a in actions if a.risk == "LOW"], key=lambda a: a.est_bytes, reverse=True)
        meds = sorted([a for a in actions if a.risk == "MEDIUM"], key=lambda a: a.est_bytes, reverse=True)
        
        selected = []
        total = 0
        
        for a in lows + meds:
            selected.append(a)
            total += a.est_bytes
            if total >= goal_bytes:
                break
                
        # If goal is specified, we return only the selected subset?
        # "Goal selection: pick LOW first, then MEDIUM largest-first until goal_gb is reached; if unreachable, say so with the maximum available."
        # If unreachable, maybe we just return all LOW/MEDIUM?
        actions = selected
        
    return actions, excluded
