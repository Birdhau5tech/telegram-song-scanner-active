<#
Setup script for Windows: enables script execution for the current user,
creates a virtual environment, activates it, upgrades pip and installs
requirements from requirements.txt.

Usage (PowerShell):
  Open PowerShell (no admin required), then run:
    .\scripts\setup\setup_windows_env.ps1

Notes:
- This sets the ExecutionPolicy for the CurrentUser only (RemoteSigned).
- If your organization blocks changing the policy, run the commands manually.
#>

try {
    # Ensure we're running from the repository root
    $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
    Set-Location -Path (Resolve-Path "$scriptPath\..\..")

    Write-Host "Setting ExecutionPolicy for CurrentUser to RemoteSigned..."
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force

    if (-not (Test-Path -Path ".venv")) {
        Write-Host "Creating virtual environment .venv..."
        python -m venv .venv
    } else {
        Write-Host ".venv already exists, skipping creation."
    }

    Write-Host "Activating virtual environment..."
    . .\.venv\Scripts\Activate.ps1

    Write-Host "Upgrading pip and installing requirements..."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

    Write-Host "Setup complete. Virtual environment is active."
} catch {
    Write-Error "Setup failed: $_"
    exit 1
}
