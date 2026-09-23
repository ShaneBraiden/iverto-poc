# Simulates an IP camera: MediaMTX serves an RTSP endpoint and FFmpeg loops a clip into it.
#   .\rtsp\serve.ps1                         -> rtsp://localhost:8554/cam1
#   .\rtsp\serve.ps1 -Video path\to\clip.mp4 -Path cam2
param(
    [string]$Video = "$PSScriptRoot\..\data\samples\people-walking.mp4",
    [string]$Path = "cam1"
)
$ErrorActionPreference = "Stop"
$version = "v1.21.0"
$bin = Join-Path $PSScriptRoot "bin"
$mediamtx = Join-Path $bin "mediamtx.exe"

if (-not (Test-Path $mediamtx)) {
    Write-Host "Downloading MediaMTX $version..."
    New-Item -ItemType Directory -Force $bin | Out-Null
    $zip = Join-Path $bin "mediamtx.zip"
    Invoke-WebRequest "https://github.com/bluenviron/mediamtx/releases/download/$version/mediamtx_${version}_windows_amd64.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $bin -Force
    Remove-Item $zip, (Join-Path $bin "mediamtx.yml")  # we pass our own config
}

# Use ffmpeg from PATH, else the binary bundled with the backend's imageio-ffmpeg package.
$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ffmpeg) {
    $py = Join-Path $PSScriptRoot "..\backend\.venv\Scripts\python.exe"
    $ffmpeg = & $py -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
}

$server = Start-Process $mediamtx -ArgumentList "`"$PSScriptRoot\mediamtx.yml`"" -PassThru -NoNewWindow
try {
    Start-Sleep -Seconds 1
    Write-Host "Streaming $Video -> rtsp://localhost:8554/$Path  (Ctrl+C to stop)"
    & $ffmpeg -hide_banner -loglevel warning -re -stream_loop -1 -i $Video -c copy -f rtsp -rtsp_transport tcp "rtsp://localhost:8554/$Path"
}
finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
