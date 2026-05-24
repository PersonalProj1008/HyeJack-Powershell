### Building the Executable

This project includes a custom PyInstaller `.spec` file to properly bundle interactive prompt libraries (`inquirer`, `prompt_toolkit`, etc.).

#### Build Instructions (Using Ubuntu Container - Recommended)

The cleanest and most reliable way to build this project is inside an **Ubuntu Docker container**.

1. Make sure you have **Docker** installed and running.

2. Open a terminal in the project root folder (where `HyeJack-Powershell.py` and `HyeJack-Powershell.spec` are located).

3. Run the following command:

```bash
docker run --rm -v "$(pwd):/src" -w /src ubuntu:22.04 sh -c '
    apt-get update && \
    apt-get install -y python3 python3-pip python3-venv gcc libpq-dev binutils && \
    python3 -m pip install --upgrade pip && \
    pip3 install pyinstaller && \
    pip3 install -r requirements.txt && \
    pyinstaller --clean HyeJack-Powershell.spec
'
```

After the build finishes, the executable will be located at:

```
dist/HyeJack-Powershell/HyeJack-Powershell
```

> **Note**: This builds a Linux executable. It will **not** run on Windows.

---

#### Local Build (Alternative)

If you prefer to build directly on your machine:

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --clean HyeJack-Powershell.spec
```

---

**Output Location**:  
The final executable is in the `dist/HyeJack-Powershell/` folder.

---
