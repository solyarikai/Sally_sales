import os
import json
from pathlib import Path

# --- Настройки Exa MCP ---
EXA_API_KEY = "197fc32a-3563-4e29-bdb1-5f5a796034c9" 

def update_json_file(file_path, update_func):
    path = Path(file_path).expanduser()
    if not path.parent.exists():
        print(f"⚠️  Директория {path.parent} не найдена. Пропускаем.")
        return False
    
    data = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Ошибка парсинга {path}. Файл поврежден.")
            data = {}

    new_data = update_func(data)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Успешно обновлен: {path}")
    return True

def update_claude_desktop(data):
    if "mcpServers" not in data:
        data["mcpServers"] = {}
    data["mcpServers"]["exa"] = {
        "command": "npx",
        "args": ["-y", "@exa/mcp-server"],
        "env": { "EXA_API_KEY": EXA_API_KEY }
    }
    return data

def update_continue(data):
    if "contextProviders" not in data:
        data["contextProviders"] = []
    
    exa_site = {
        "id": "exa",
        "type": "command",
        "command": "npx",
        "args": ["-y", "@exa/mcp-server"],
        "env": { "EXA_API_KEY": EXA_API_KEY }
    }
    
    mcp_provider = next((p for p in data["contextProviders"] if p.get("name") == "mcp"), None)
    
    if mcp_provider:
        if "options" not in mcp_provider: mcp_provider["options"] = {}
        if "sites" not in mcp_provider["options"]: mcp_provider["options"]["sites"] = []
        sites = mcp_provider["options"]["sites"]
        if not any(s.get("id") == "exa" for s in sites):
            sites.append(exa_site)
    else:
        data["contextProviders"].append({
            "name": "mcp",
            "options": { "sites": [exa_site] }
        })
    return data

if __name__ == "__main__":
    print("🚀 Настройка Exa MCP во всех инструментах...")
    update_json_file("~/Library/Application Support/Claude/claude_desktop_config.json", update_claude_desktop)
    update_json_file("~/.continue/config.json", update_continue)
    print("\n✨ Готово! Пожалуйста, перезапустите программы.")
