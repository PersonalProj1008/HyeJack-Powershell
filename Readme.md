# HyeJack-Powershell — Usage Guide

## What It Is

HyeJack-Powershell is an **AI-powered agentic automation tool** that uses xAI's Grok LLM to generate, execute, and self-heal **PowerShell scripts** from natural language.

It turns your requests into structured, executable workflows with built-in error correction, file awareness, and tool usage.

### Benefits of HyeJack-Powershell

HyeJack-Powershell is designed as a **simple yet powerful AI assistant** that helps you get real work done through natural language. Here’s what makes it useful:

- **Natural Language to Working Scripts**  
  Describe what you want in plain English, and Jack generates ready-to-run PowerShell scripts for automation, file management, coding tasks, backups, monitoring, and more.

- **Self-Healing Capability**  
  If a generated script fails, Jack automatically analyzes the error and retries by fixing only the problematic step — up to 20 times by default. This makes automation more reliable without manual debugging.

- **Smart Knowledge Base (RAG)**  
  Jack can understand and reference your project files and documents. It automatically detects, uploads, and tracks changes to your files using Grok Collections, so you can ask questions like “Summarize my Python codebase” or “Find issues in my project”.

- **Organized Work with Topics**  
  Keep different projects or conversations separate using topics. Each topic has its own persistent chat history and dedicated knowledge base collection.

- **Powerful Tool Integration**  
  Combine real-time web search, X (Twitter) search, code execution, and your own documents in a single request using simple flags like `--fullpower`.

- **Polished and Easy to Use**  
  Beautiful terminal interface with progress bars, typing effects, and clear feedback. Interactive menus make selecting topics and managing credentials simple.

- **Runs Securely in Docker**  
  Fully containerized setup with PostgreSQL for memory and PowerShell 7 for execution — isolated, reproducible, and safe.

- **Highly Customizable**  
  You can easily modify the system prompts in `hyejack_powershell.toml` to change Jack’s behavior, tone, or specialization to better suit your workflow.

---

## Docker Setup (Recommended)

```bash
# Start services
docker compose up -d postgres pwsh-client

# Enter PowerShell environment
docker compose exec pwsh-client pwsh
```

All commands below must be run **inside the `pwsh-client` container**.

---

## Core Commands

### 1. Setup Credentials

```powershell
HyeJack-Powershell --CREDENTIALS
```

### 2. Select Topic

```powershell
HyeJack-Powershell --SIDEBAR
```

### 3. Main Command

```powershell
HyeJack-Powershell --HYE_JACK "Your request here"
```

---

## Customizing Behavior

You can freely customize the system prompts inside **`hyejack_powershell.toml`** to change Jack’s personality, style, or behavior.

However, **the output JSON structure must remain exactly the same**. The Python backend strictly expects a specific format.

### Required JSON Output Structure

Grok must always return valid JSON matching one of these two patterns:

#### 1. For Action / Workflow Requests (Most Common)

```json
{
  "Agentic_Data": {
    "step": {
      "1": {
        "use_env": [],
        "step_name": "Brief step description",
        "1": "Write-Host \"Doing something...\" -ForegroundColor Green",
        "2": "Your PowerShell command here",
        "steps_to_not_include": []
      },
      "2": {
        "use_env": ["step.1"],
        "step_name": "Next step",
        "1": "Another command...",
        "steps_to_not_include": ["3"]
      }
    }
  },
  "Info_Data": {
    "1": {
      "type": "text",
      "value": "Short summary of what this workflow does"
    }
  }
}
```

#### 2. For Pure Informational Queries

```json
{
  "Agentic_Data": null,
  "Info_Data": {
    "1": {
      "type": "text",
      "value": "Your detailed response here..."
    }
  }
}
```

> **Important**: Do not change the keys `Agentic_Data`, `Info_Data`, `step`, `use_env`, `step_name`, or `steps_to_not_include`.
> The self-healing and script generation logic depends on this exact structure.

---

## File Support (Knowledge Base / RAG)

Jack can analyze and reference files from your topic’s collection.

**Supported Formats:**

- Documents: `.pdf`, `.doc`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.yaml`, `.html`, etc.
- Code files: `.py`, `.js`, `.ts`, `.cs`, `.go`, `.java`, `.ps1`, etc.
- Office files: `.xlsx`, `.pptx`, etc.

**Not Supported:**

- Direct image files (`.jpg`, `.png`, `.gif`, `.webp`, etc.)

> **Note**: Images embedded inside PDFs **are supported** (Grok can extract and reason about them).
> Standalone image files are **not** supported at this time.

---

## Tool Flags (Combine with `--HYE_JACK`)

| Flag                     | Description                                                |
| ------------------------ | ---------------------------------------------------------- |
| `--WEBSEARCH`            | Enable real-time web search                                |
| `--XSEARCH`              | Enable X (Twitter) search                                  |
| `--COMPUTATIONALABILITY` | Enable Grok’s code interpreter                             |
| `--COLLECTIONREF`        | Enable retrieval from current topic’s knowledge base (RAG) |
| `--RETRIVALCOUNT N`      | Number of chunks to retrieve (default: 1, max: 40)         |

### Full Power Modes

| Flag            | Description                          | Max Results |
| --------------- | ------------------------------------ | ----------- |
| `--FULLPOWER`   | Enables **all tools** at once        | 25          |
| `--FULLPOWER2X` | Enables all tools with higher limits | 50          |

---

## Chat History Flags

| Flag               | History Sent to Grok |
| ------------------ | -------------------- |
| `--MINCHATHISTORY` | Last 5 messages      |
| `--AVGCHATHISTORY` | Last 10 messages     |
| `--MAXCHATHISTORY` | Last 20 messages     |

---

## Additional Options

| Flag                         | Description                  | Default                     |
| ---------------------------- | ---------------------------- | --------------------------- |
| `--DefaultLoc <path>`        | Directory for JSON & scripts | `./`                        |
| `--CONFIGURATIONFILE <path>` | TOML config file path        | `./hyejack_powershell.toml` |
| `--TRYCOUNT <number>`        | Max self-healing attempts    | `20`                        |

---

## Full Practical Examples

```powershell
# Create automation scripts
HyeJack-Powershell --HYE_JACK "Create a PowerShell script that backs up important folders daily and deletes old backups older than 30 days"

# Coding help
HyeJack-Powershell --HYE_JACK "Generate a complete FastAPI backend with user authentication and PostgreSQL integration"

# Analyze files + research
HyeJack-Powershell --HYE_JACK "Review my Python project and suggest performance improvements based on latest best practices" `
  --fullpower --COLLECTIONREF --AVGCHATHISTORY
```

---

## How Self-Healing Works

When a generated PowerShell script fails:

1. The error and context are sent back to Grok
2. Grok corrects **only the failing step**
3. The workflow is re-executed
4. This repeats up to `--TRYCOUNT` times

This makes Jack highly reliable for real-world automation.

---

## Quick Tips

- Always start with `--CREDENTIALS` and `--SIDEBAR`
- Customize prompts in `hyejack_powershell.toml` to match your style
- Keep the **JSON output structure unchanged**
- Use `--fullpower` for complex or research-heavy tasks
- Jack works best with documents and code — not standalone images

---

**Jack is essentially a self-correcting automation engineer living inside PowerShell.**
Give it clear tasks and watch it build, fix, and improve scripts for you.
