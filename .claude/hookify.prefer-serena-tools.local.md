---
name: prefer-serena-tools
enabled: true
event: bash
pattern: \b(find|cat|head|tail|grep|rg)\s+
action: warn
---

**Prefer Serena MCP tools over bash for file operations**

You're using a bash command for file operations. Serena MCP tools are more optimal for this project:

**Instead of:**
- `find` / `ls` → Use `mcp__serena.find_files` or `Glob`
- `cat` / `head` / `tail` → Use `mcp__serena.read_file` or `Read`
- `grep` / `rg` → Use `mcp__serena.search_text` or `Grep`

Serena tools provide better integration, caching, and context awareness for this codebase.
