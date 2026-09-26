# Jagiye Maa Kiran - Autonomous Windows Startup Priming Script
# Executed automatically at Windows logon or PC startup

$ProjectDir = "C:\Users\admin\Downloads\NGO AI LLM"
$LogDir = Join-Path $ProjectDir ".serena\logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$LogFile = Join-Path $LogDir "jagiye_maakiran_startup.log"

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$LogEntry = "[$Timestamp] [Jagiye Maa Kiran] PC Startup Priming Triggered.`n"

# Verify Project Root
if (Test-Path (Join-Path $ProjectDir ".serena\project.yml")) {
    $LogEntry += "[$Timestamp] [Jagiye Maa Kiran] Project configuration verified at $ProjectDir.`n"
} else {
    $LogEntry += "[$Timestamp] [Jagiye Maa Kiran] WARNING: .serena\project.yml not found.`n"
}

# Verify Core Memories
$CoreMems = @('core', 'local_memory', 'tech_stack', 'suggested_commands', 'conventions', 'task_completion', 'memory_maintenance')
$MemCount = 0
foreach ($m in $CoreMems) {
    if (Test-Path (Join-Path $ProjectDir ".serena\memories\$m.md")) {
        $MemCount++
    }
}
$LogEntry += "[$Timestamp] [Jagiye Maa Kiran] Serena Memories: $MemCount/$($CoreMems.Count) online.`n"

# Check Graphify AST
if (Test-Path (Join-Path $ProjectDir "graphify-out\graph.json")) {
    $LogEntry += "[$Timestamp] [Jagiye Maa Kiran] Graphify AST knowledge graph present.`n"
}

$LogEntry += "[$Timestamp] [Jagiye Maa Kiran] System Status: PRIMED & READY.`n--------------------------------------------------`n"
Add-Content -Path $LogFile -Value $LogEntry -Encoding UTF8
