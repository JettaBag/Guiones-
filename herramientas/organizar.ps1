# organizar.ps1 - crea Escritorio\editor-videos y ordena tus videos/audios (solo COPIA, nunca mueve ni borra)
#
# Paso 1:  powershell -ExecutionPolicy Bypass -File organizar.ps1
#          -> crea las carpetas y escribe lista.csv con los videos y audios de los ultimos 60 dias
#             (Descargas, Escritorio y Videos). Abre lista.csv y en la columna "destino" escribe:
#             referencias, crudos o sonidos (deja vacio lo que no quieras copiar).
# Paso 2:  powershell -ExecutionPolicy Bypass -File organizar.ps1 -Copiar
#          -> copia cada archivo marcado a su carpeta. Los originales no se tocan.
param([switch]$Copiar, [int]$Dias = 60)

$escritorio = [Environment]::GetFolderPath("Desktop")
$base = Join-Path $escritorio "editor-videos"
$sub = "referencias", "crudos", "sonidos", "salida"
foreach ($s in $sub) { New-Item -ItemType Directory -Force -Path (Join-Path $base $s) | Out-Null }
$lista = Join-Path $base "lista.csv"

if (-not $Copiar) {
    $origenes = @(
        (Join-Path $env:USERPROFILE "Downloads"),
        $escritorio,
        [Environment]::GetFolderPath("MyVideos")
    ) | Where-Object { Test-Path $_ }
    $ext = ".mp4", ".mov", ".mp3", ".wav"
    $desde = (Get-Date).AddDays(-$Dias)
    $archivos = foreach ($o in $origenes) {
        Get-ChildItem -Path $o -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $ext -contains $_.Extension.ToLower() -and $_.LastWriteTime -ge $desde -and
                           $_.FullName -notlike "$base*" }
    }
    $archivos = $archivos | Sort-Object LastWriteTime -Descending
    $i = 0
    $filas = foreach ($a in $archivos) {
        $i++
        [pscustomobject]@{
            n = $i; nombre = $a.Name; tipo = $a.Extension.TrimStart(".").ToLower()
            mb = [math]::Round($a.Length / 1MB, 1); fecha = $a.LastWriteTime.ToString("yyyy-MM-dd HH:mm")
            destino = ""; ruta = $a.FullName
        }
    }
    $filas | Export-Csv -Path $lista -NoTypeInformation -Encoding UTF8
    $filas | Format-Table n, nombre, tipo, mb, fecha -AutoSize
    Write-Host ""
    Write-Host "Carpeta creada: $base"
    Write-Host "Lista guardada en: $lista  ($i archivos)"
    Write-Host "Escribe en la columna 'destino': referencias, crudos o sonidos. Luego corre este script con -Copiar."
    exit
}

if (-not (Test-Path $lista)) { Write-Host "No existe $lista. Corre primero el script sin -Copiar."; exit 1 }
$ok = 0
foreach ($f in (Import-Csv $lista)) {
    $d = $f.destino.Trim().ToLower()
    if ($d -eq "") { continue }
    if ($sub -notcontains $d -or $d -eq "salida") { Write-Host "Destino no valido en fila $($f.n): '$d'"; continue }
    $dst = Join-Path (Join-Path $base $d) $f.nombre
    if (Test-Path $dst) { Write-Host "Ya existe, no se sobrescribe: $dst"; continue }
    Copy-Item -LiteralPath $f.ruta -Destination $dst
    $ok++; Write-Host "Copiado -> $d\$($f.nombre)"
}
Write-Host "$ok archivos copiados. Los originales siguen en su lugar."
