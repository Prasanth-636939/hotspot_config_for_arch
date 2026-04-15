# Maintainer: Your Name <your.email@example.com>
pkgname=hotspot-gui-git
pkgver=0.1.0
pkgrel=1
pkgdesc="Arch Linux Wi-Fi Hotspot Orchestrator and GUI via NetworkManager D-Bus"
arch=('any')
url="https://github.com/Prasanth-636939/hotspot_config_for_arch.git"
license=('GPL-3.0-or-later') # Update with your actual license
depends=(
    'python'
    'python-pyqt6'
    'python-sdbus'
    'python-sdbus-networkmanager-git'
)
makedepends=(
    'git'
    'python-build'
    'python-installer'
    'python-wheel'
    'python-setuptools'
)
provides=("hotspot-gui")
conflicts=("hotspot-gui")
source=("hotspot-gui::git+file://${PWD}")
sha256sums=('SKIP')

pkgver() {
    cd "$srcdir/hotspot-gui"
    printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

build() {
    cd "$srcdir/hotspot-gui"
    python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/hotspot-gui"
    python -m installer --destdir="$pkgdir" dist/*.whl
    
    # Install the desktop entry
    install -Dm644 "hotspot-manager.desktop" "$pkgdir/usr/share/applications/hotspot-manager.desktop"
    
    # Optional: Install documentation/readme
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}
