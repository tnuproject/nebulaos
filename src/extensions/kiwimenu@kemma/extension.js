/*
 * Kiwi Menu for NebulaOS (GNOME 43 Compatible)
 * Top-left system menu replacing Activities with the NebulaOS symbol.
 */

const { Clutter, Gio, GLib, GObject, St, Meta, Shell } = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();

const KiwiMenuButton = GObject.registerClass(
class KiwiMenuButton extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'KiwiMenu');

        let icon = new St.Icon({
            icon_name: 'nebulaos-symbol',
            fallback_icon_name: 'distributor-logo',
            icon_size: 18,
            style_class: 'system-status-icon',
        });
        this.add_child(icon);

        this._buildMenu();
    }

    _buildMenu() {
        // About This Computer / NebulaOS
        let aboutItem = new PopupMenu.PopupMenuItem('About NebulaOS');
        aboutItem.connect('activate', () => {
            GLib.spawn_command_line_async('gnome-control-center info-overview');
        });
        this.menu.addMenuItem(aboutItem);

        // System Settings
        let settingsItem = new PopupMenu.PopupMenuItem('System Settings…');
        settingsItem.connect('activate', () => {
            GLib.spawn_command_line_async('gnome-control-center');
        });
        this.menu.addMenuItem(settingsItem);

        // App Store
        let storeItem = new PopupMenu.PopupMenuItem('App Store…');
        storeItem.connect('activate', () => {
            GLib.spawn_command_line_async('gnome-software');
        });
        this.menu.addMenuItem(storeItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Sleep
        let sleepItem = new PopupMenu.PopupMenuItem('Sleep');
        sleepItem.connect('activate', () => {
            GLib.spawn_command_line_async('systemctl suspend');
        });
        this.menu.addMenuItem(sleepItem);

        // Restart
        let restartItem = new PopupMenu.PopupMenuItem('Restart…');
        restartItem.connect('activate', () => {
            let sm = imports.misc.loginManager ? imports.misc.loginManager.getLoginManager() : null;
            if (sm) sm.reboot();
            else GLib.spawn_command_line_async('systemctl reboot');
        });
        this.menu.addMenuItem(restartItem);

        // Shut Down
        let shutdownItem = new PopupMenu.PopupMenuItem('Shut Down…');
        shutdownItem.connect('activate', () => {
            let sm = imports.misc.loginManager ? imports.misc.loginManager.getLoginManager() : null;
            if (sm) sm.powerOff();
            else GLib.spawn_command_line_async('systemctl poweroff');
        });
        this.menu.addMenuItem(shutdownItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Lock Screen
        let lockItem = new PopupMenu.PopupMenuItem('Lock Screen');
        lockItem.connect('activate', () => {
            if (Main.screenShield) Main.screenShield.lock(true);
        });
        this.menu.addMenuItem(lockItem);

        // Log Out
        let logoutItem = new PopupMenu.PopupMenuItem('Log Out…');
        logoutItem.connect('activate', () => {
            try {
                let endSessionDialog = imports.ui.endSessionDialog;
                if (endSessionDialog) {
                    let dialog = new endSessionDialog.EndSessionDialog();
                    dialog.open(endSessionDialog.DialogType.LOGOUT);
                    return;
                }
            } catch (e) {}
            GLib.spawn_command_line_async('gnome-session-quit --logout');
        });
        this.menu.addMenuItem(logoutItem);
    }
});

let _indicator = null;

function init() {
}

function enable() {
    try {
        _indicator = new KiwiMenuButton();
        Main.panel.addToStatusArea('kiwimenu', _indicator, 0, 'left');

        if (Main.panel.statusArea.activities) {
            Main.panel.statusArea.activities.container.hide();
        }
    } catch (e) {
        log(`[KiwiMenu] enable error: ${e}`);
    }
}

function disable() {
    if (_indicator) {
        _indicator.destroy();
        _indicator = null;
    }
    if (Main.panel.statusArea.activities) {
        Main.panel.statusArea.activities.container.show();
    }
}
