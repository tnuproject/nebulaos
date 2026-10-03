project('gtk4-ding',
  version: '1',
  license: 'GPL3'
)

gnome = import ('gnome')
i18n = import('i18n')

prefix = get_option('prefix')
datadir = join_paths (prefix, get_option('datadir'))
schema_dir = join_paths(datadir, 'glib-2.0', 'schemas')

extensions_dir = join_paths(prefix, 'share', 'gnome-shell', 'extensions', 'gtk4-ding@smedius.gitlab.com')

install_data([
    'emulateX11WindowType.js',
    'extension.js',
    'gnomeShellOverride.js',
    'metadata.json',
    'prefs.js',
    'visibleArea.js'
  ],
  install_dir: extensions_dir
)

install_subdir(
  'app',  install_dir: extensions_dir
)

install_subdir(
  'utils',  install_dir: extensions_dir
)

subdir(
  'po'
)
subdir(
  'schemas'
)

meson.add_install_script('scripts/meson_post_install.py')
