/*
 * Kiwi Extension for NebulaOS (GNOME 43 Compatible)
 * General desktop enhancements: skips overview on login, focuses windows,
 * and manages window controls parity.
 */

const { GLib, Gio, Clutter, Meta, Shell } = imports.gi;
const Main = imports.ui.main;
const ExtensionUtils = imports.misc.extensionUtils;

let _windowCreatedId = null;

function init() {
}

function enable() {
    // 1. Skip initial overview on login
    GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
        try {
            if (Main.layoutManager && Main.layoutManager.isInitialized && Main.overview.visible) {
                Main.overview.hide();
            }
        } catch (e) {}
        return GLib.SOURCE_REMOVE;
    });

    // 2. Focus on newly launched windows
    if (global.display) {
        _windowCreatedId = global.display.connect('window-created', (display, window) => {
            if (window && !window.is_override_redirect()) {
                GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                    try {
                        window.activate(global.get_current_time());
                    } catch (e) {}
                    return GLib.SOURCE_REMOVE;
                });
            }
        });
    }
}

function disable() {
    if (_windowCreatedId && global.display) {
        global.display.disconnect(_windowCreatedId);
        _windowCreatedId = null;
    }
}