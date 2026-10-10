[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RutaIso,
    [Parameter(Mandatory = $true)][string]$AdaptadorPuente,
    [string]$DirectorioVm = (Join-Path $env:USERPROFILE 'VirtualBox VMs'),
    [string]$VBoxManage = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $VBoxManage -PathType Leaf)) {
    throw 'Instalar VirtualBox antes de crear las VM.'
}
if (-not (Test-Path -LiteralPath $RutaIso -PathType Leaf) -or [IO.Path]::GetExtension($RutaIso) -ne '.iso') {
    throw 'Indicar la ISO de Ubuntu Server AMD64 existente.'
}
$rutaIsoCompleta = (Resolve-Path -LiteralPath $RutaIso).Path
$directorioCompleto = [IO.Path]::GetFullPath($DirectorioVm)

function Ejecutar-VirtualBox {
    param([string[]]$Argumentos)
    $salida = & $VBoxManage @Argumentos 2>&1
    if ($LASTEXITCODE -ne 0) { throw "VirtualBox no pudo completar la operación: $salida" }
    return $salida
}

$adaptadores = Ejecutar-VirtualBox -Argumentos @('list', 'bridgedifs')
$nombresAdaptadores = @($adaptadores | ForEach-Object {
    if ($_ -match '^Name:\s+(.+)$') { $Matches[1].Trim() }
})
if ($AdaptadorPuente -notin $nombresAdaptadores) {
    throw "No existe el adaptador puente indicado. Opciones: $($nombresAdaptadores -join ', ')"
}
$existentes = Ejecutar-VirtualBox -Argumentos @('list', 'vms')
foreach ($nombre in @('worker-01', 'worker-02')) {
    if (@($existentes | Where-Object { $_ -match ('^"' + [regex]::Escape($nombre) + '" ') }).Count -gt 0 -or
        (Test-Path -LiteralPath (Join-Path $directorioCompleto $nombre))) {
        throw "Ya existe $nombre o su carpeta. No se modificaron las VM existentes."
    }
}

foreach ($nombre in @('worker-01', 'worker-02')) {
    Ejecutar-VirtualBox -Argumentos @('createvm', '--name', $nombre, '--ostype', 'Ubuntu_64', '--basefolder', $directorioCompleto, '--register')
    Ejecutar-VirtualBox -Argumentos @('modifyvm', $nombre, '--memory', '2048', '--cpus', '2', '--ioapic', 'on', '--graphicscontroller', 'vmsvga', '--boot1', 'dvd', '--boot2', 'disk', '--nic1', 'bridged', '--bridgeadapter1', $AdaptadorPuente, '--cableconnected1', 'on')
    $disco = Join-Path (Join-Path $directorioCompleto $nombre) "$nombre.vdi"
    Ejecutar-VirtualBox -Argumentos @('createmedium', 'disk', '--filename', $disco, '--size', '12288', '--format', 'VDI')
    Ejecutar-VirtualBox -Argumentos @('storagectl', $nombre, '--name', 'SATA', '--add', 'sata', '--controller', 'IntelAhci')
    Ejecutar-VirtualBox -Argumentos @('storageattach', $nombre, '--storagectl', 'SATA', '--port', '0', '--device', '0', '--type', 'hdd', '--medium', $disco)
    Ejecutar-VirtualBox -Argumentos @('storageattach', $nombre, '--storagectl', 'SATA', '--port', '1', '--device', '0', '--type', 'dvddrive', '--medium', $rutaIsoCompleta)
}
Write-Host 'VM creadas y apagadas. Abrir VirtualBox e instalar Ubuntu en cada consola. No se modificó la red de Windows.'
