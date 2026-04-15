# Maintainer: Your Name <your.email@example.com>
pkgname=hotspot-gui-git
pkgver=r5.2029f13
pkgrel=1
pkgdesc="Arch Linux Wi-Fi Hotspot Orchestrator and GUI via NetworkManager D-Bus"
arch=('any')
url="https://github.com/Prasanth-636939/hotspot_config_for_arch"
license=('GPL-3.0-or-later')
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
source=("hotspot-gui::git+https://github.com/Prasanth-636939/hotspot_config_for_arch.git")
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
    
    # Symlink to match previous bash script
    install -d "$pkgdir/usr/bin"
    ln -sf "/usr/bin/hotspot-gui" "$pkgdir/usr/bin/hotspot"
    
    # Install the desktop entry
    install -Dm644 "hotspot-manager.desktop" "$pkgdir/usr/share/applications/hotspot-manager.desktop"
    
    # documentation/readme and license
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
