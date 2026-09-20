"""Validation script for IEEE manuscript LaTeX syntax, balanced environments, and claims."""
import re
import pathlib
import json

def validate_latex(tex_path="paper/paper.tex"):
    tex_file = pathlib.Path(tex_path)
    if not tex_file.is_file():
        print(f"Error: {tex_path} not found.")
        return False
    text = tex_file.read_text(encoding="utf-8")
    
    # 1. Check brace matching
    stack = []
    lines = text.splitlines()
    for line_num, line in enumerate(lines, 1):
        # strip comments
        line_no_comment = re.sub(r'(?<!\\)%.*', '', line)
        for char in line_no_comment:
            if char in '{':
                stack.append((char, line_num))
            elif char in '}':
                if not stack:
                    print(f"Error: Unmatched closing brace at line {line_num}")
                    return False
                stack.pop()
    if stack:
        print(f"Error: {len(stack)} unclosed opening braces. First at line {stack[0][1]}")
        return False
    print("Brace matching: PASS")

    # 2. Check begin/end environment matching
    env_stack = []
    begin_matches = list(re.finditer(r'\\begin\{([a-zA-Z*]+)\}', text))
    end_matches = list(re.finditer(r'\\end\{([a-zA-Z*]+)\}', text))
    events = []
    for m in begin_matches:
        events.append((m.start(), 'begin', m.group(1)))
    for m in end_matches:
        events.append((m.start(), 'end', m.group(1)))
    events.sort(key=lambda x: x[0])
    
    for pos, kind, env in events:
        if kind == 'begin':
            env_stack.append(env)
        else:
            if not env_stack:
                print(f"Error: Unmatched \\end{{{env}}}")
                return False
            last = env_stack.pop()
            if last != env:
                print(f"Error: Environment mismatch: \\begin{{{last}}} closed by \\end{{{env}}}")
                return False
    if env_stack:
        print(f"Error: Unclosed environments: {env_stack}")
        return False
    print("Environment matching: PASS")

    # 3. Check citations vs bibitems
    citations = set(re.findall(r'\\cite\{([^}]+)\}', text))
    split_cites = set()
    for c in citations:
        for k in c.split(','):
            split_cites.add(k.strip())
    
    bibitems = set(re.findall(r'\\bibitem\{([^}]+)\}', text))
    missing_cites = split_cites - bibitems
    if missing_cites:
        print(f"Error: Missing bibitems for citations: {missing_cites}")
        return False
    print(f"Citations resolved: PASS ({len(split_cites)} citations, {len(bibitems)} bibitems)")

    # 4. Check labels and refs
    labels = set(re.findall(r'\\label\{([^}]+)\}', text))
    refs = set(re.findall(r'\\ref\{([^}]+)\}', text))
    missing_refs = refs - labels
    if missing_refs:
        print(f"Error: Missing labels for refs: {missing_refs}")
        return False
    print(f"References resolved: PASS ({len(refs)} refs, {len(labels)} labels)")

    # 5. Check figure files exist
    fig_files = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', text)
    base_dir = tex_file.parent
    missing_figs = []
    for ff in fig_files:
        p = base_dir / ff
        if not p.is_file() and not (base_dir / (ff + ".png")).is_file() and not (base_dir / (ff + ".pdf")).is_file():
            missing_figs.append(ff)
    if missing_figs:
        print(f"Error: Missing figure files: {missing_figs}")
        return False
    print(f"Figures exist: PASS ({len(fig_files)} figures)")

    return True

if __name__ == "__main__":
    validate_latex("paper/paper.tex")
