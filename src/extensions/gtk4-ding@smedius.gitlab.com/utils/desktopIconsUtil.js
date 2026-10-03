/* DING: Desktop Icons New Generation for GNOME Shell
 *
 * Copyright (C) 2022 Sundeep Mediratta - eslint fix errors and format GJS/Gnome guidelines
 * Copyright (C) 2019 Sergio Costas (rastersoft@gmail.com)
 * Based on code original (C) Carlos Soriano
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

imports.gi.versions.GdkX11 = '4.0';
imports.gi.versions.Gdk = '4.0';
const { Gio, GLib } = imports.gi;
const ByteArray = imports.byteArray;

const Prefs = imports.app.preferences;
const Enums = imports.app.enums;
const FileUtils = imports.utils.fileUtils;
var applicationid = null;
var usingX11 = null;

const Gettext = imports.gettext.domain('gtk4-ding');

const _ = Gettext.gettext;

/**
 * Sets the Gtk appid variable for the rest of the functions in the file
 *
 * @param {string} appid The current application ID
 */
function setApplicationId(appid) {
    applicationid = appid;
}

/**
 * Returs the Gtk Application ID set prior or null
 */
function getApplicationID() {
    return applicationid;
}

/**
 *
 * Returns the user desktop directory as a Gio.File
 */
function getDesktopDir() {
    let desktopPath = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP);
    return Gio.File.new_for_commandline_arg(desktopPath);
}

/**
 *
 * Returns the Nautilus scripts directory as a Gio.File
 */
function getScriptsDir() {
    let scriptsDir =  GLib.build_filenamev([GLib.get_home_dir(), Enums.NAUTILUS_SCRIPTS_DIR]);
    return Gio.File.new_for_commandline_arg(scriptsDir);
}

/**
 *
 * Returns the users Templates directory as a Gio.File
 */
function getTemplatesDir() {
    let templatesDir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_TEMPLATES);
    if ((templatesDir === GLib.get_home_dir()) || (templatesDir === null))
        return null;

    return Gio.File.new_for_commandline_arg(templatesDir);
}

/**
 *
 * @param {float} value number
 * @param {integer}  min number
 * @param {integer} max number
 */
function clamp(value, min, max) {
    return Math.max(Math.min(value, max), min);
}

/**
 *
 * @param {string} commandLine command to execute
 * @param {Array} environ child's environment, or <code>null</code> to inherit parent's
 */
function spawnCommandLine(commandLine, environ = null) {
    try {
        let argv = GLib.shell_parse_argv(commandLine).slice(1);
        trySpawn(null, argv, environ);
    } catch (e) {
        logError(e, `${commandLine} failed with ${e}`);
    }
}

/**
 *
 * @param {string} workdir working directory path
 * @param {string} command command to exectue
 */
function launchTerminal(workdir, command) {
    let terminalSettings = new Gio.Settings({ schema_id: Enums.TERMINAL_SCHEMA });
    let exec = terminalSettings.get_string(Enums.EXEC_KEY);
    let argv = [exec, `--working-directory=${workdir}`];
    if (command) {
        argv.push('-e');
        argv.push(command);
    }
    trySpawn(workdir, argv, null);
}

/**
 *
 * @param {string} workdir working directory path
 * @param  {Array(String)} argv child's argument vector
 * @param {Array} environ child's environment, or <code>null</code> to inherit parent's
 */
function trySpawn(workdir, argv, environ = null) {
    /* The following code has been extracted from GNOME Shell's
     * source code in Misc.Util.trySpawn function and modified to
     * set the working directory.
     *
     * https://gitlab.gnome.org/GNOME/gnome-shell/blob/gnome-3-30/js/misc/util.js
     */

    var pid;
    try {
        pid = GLib.spawn_async(workdir, argv, environ,
            GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            null).slice(1);
    } catch (err) {
        /* Rewrite the error in case of ENOENT */
        if (err.matches(GLib.SpawnError, GLib.SpawnError.NOENT)) {
            throw new GLib.SpawnError({
                code: GLib.SpawnError.NOENT,
                message: _('Command not found'),
            });
        } else if (err instanceof GLib.Error) {
            // The exception from gjs contains an error string like:
            //   Error invoking GLib.spawn_command_line_async: Failed to
            //   execute child process "foo" (No such file or directory)
            // We are only interested in the part in the parentheses. (And
            // we can't pattern match the text, since it gets localized.)
            let message = err.message.replace(/.*\((.+)\)/, '$1');
            throw new err.constructor({
                code: err.code,
                message,
            });
        } else {
            throw err;
        }
    }
    // Dummy child watch; we don't want to double-fork internally
    // because then we lose the parent-child relationship, which
    // can break polkit.  See https://bugzilla.redhat.com//show_bug.cgi?id=819275
    GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, () => {});
}

/**
 *
 */
function getFilteredEnviron() {
    let environ = [];
    for (let env of GLib.get_environ()) {
        /* It's a must to remove the WAYLAND_SOCKET environment variable
            because, under Wayland, DING uses an specific socket to allow the
            extension to detect its windows. But the scripts must run under
            the normal socket */
        if (env.startsWith('WAYLAND_SOCKET='))
            continue;

        environ.push(env);
    }
    return environ;
}

/**
 *
 * @param {float} x first x coordinate
 * @param {float} y first y coordinate
 * @param {float} x2 second x coordinate
 * @param {float} y2 second y coordinate
 * @returns {float} Distance between points
 */
function distanceBetweenPoints(x, y, x2, y2) {
    return Math.pow(x - x2, 2) + Math.pow(y - y2, 2);
}

/**
 *
 */
function getExtraFolders() {
    const extraFolders = [];
    if (Prefs.desktopSettings.get_boolean('show-home'))
        extraFolders.push([Gio.File.new_for_commandline_arg(GLib.get_home_dir()), Enums.FileType.USER_DIRECTORY_HOME]);

    if (Prefs.desktopSettings.get_boolean('show-trash'))
        extraFolders.push([Gio.File.new_for_uri('trash:///'), Enums.FileType.USER_DIRECTORY_TRASH]);

    return extraFolders;
}

/**
 *
 * @param {Gio.VolumeMonitor} volumeMonitor A Gio.VolumeMonitor
 */
function getMounts(volumeMonitor) {
    const showVolumes = Prefs.desktopSettings.get_boolean('show-volumes');
    const showNetwork = Prefs.desktopSettings.get_boolean('show-network-volumes');
    var mountedFileSystems;

    try {
        mountedFileSystems = volumeMonitor.get_mounts();
    } catch (e) {
        print(`Failed to get the list of mounts with ${e}`);
        return [];
    }

    let result = [];
    let uris = [];
    for (let mount of mountedFileSystems) {
        try {
            let isDrive = (mount.get_drive() !== null) || (mount.get_volume() !== null);
            let uri = mount.get_default_location().get_uri();
            if (((isDrive && showVolumes) || (!isDrive && showNetwork)) && !uris.includes(uri)) {
                result.push([mount.get_default_location(), Enums.FileType.EXTERNAL_DRIVE, mount]);
                uris.push(uri);
            }
        } catch (e) {
            print(`Failed with ${e} while getting volume`);
        }
    }
    return result;
}

/**
 *
 * @param {string} filename Name of file
 * @param {object} opts Oject with boolean option keys
 */
function getFileExtensionOffset(filename, opts = { 'isDirectory': false }) {
    let offset = filename.length;
    let extension = '';
    if (!opts.isDirectory) {
        const doubleExtensions = ['.gz', '.bz2', '.sit', '.Z', '.bz', '.xz'];
        for (const item of doubleExtensions) {
            if (filename.endsWith(item)) {
                offset -= item.length;
                extension = filename.substring(offset);
                filename = filename.substring(0, offset);
                break;
            }
        }
        let lastDot = filename.lastIndexOf('.');
        if (lastDot > 0) {
            offset = lastDot;
            extension = filename.substring(offset) + extension;
            filename = filename.substring(0, offset);
        }
    }
    return { offset, 'basename': filename, extension };
}

/**
 *
 * @param {Gio.File} file a file Gio
 * @param {stirng} contents file contents
 * @param {Gio.Cancellable} cancellable gio cancellable
 */
function replaceFileContentsAsync(file, contents, cancellable) {
    /* Promisify doesn't work with this */
    const byteArray = ByteArray.fromString(contents);

    return new Promise((resolve, reject) => {
        file.replace_contents_bytes_async(ByteArray.toGBytes(byteArray), null,
            true, Gio.FileCreateFlags.REPLACE_DESTINATION, cancellable, (sourceObject, res) => {
                try {
                    resolve(file.replace_contents_finish(res));
                } catch (e) {
                    reject(e);
                }
            });
    });
}

/**
 *
 * @param {string} text text to write in the file
 * @param {string} destinationDir path
 * @param {string} filename name of file
 * @param {Array(integer)} dropCoordinates coordiantes for the dropped file
 * @param {Gio.Cancellable} cancellable a Gio.Cancellable
 */
async function writeTextFileToPath(text, destinationDir, filename,
    dropCoordinates, cancellable = null) {
    const file = destinationDir.get_child(filename);

    try {
        await FileUtils.recursivelyMakeDir(destinationDir, cancellable);

        const info = new Gio.FileInfo();
        info.set_attribute_uint32(Gio.FILE_ATTRIBUTE_UNIX_MODE, 0o700);
        await destinationDir.set_attributes_async(info,
            Gio.FileQueryInfoFlags.NONE,
            GLib.PRIORITY_NORMAL,
            cancellable);
    } catch (e) {
        if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.EXISTS))
            throw e;
    }

    await replaceFileContentsAsync(file, text, cancellable);

    if (dropCoordinates !== null) {
        const info = new Gio.FileInfo();
        info.set_attribute_string('metadata::nautilus-drop-position',
            `${dropCoordinates.join(',')}`);

        await file.set_attributes_async(info,
            Gio.FileQueryInfoFlags.NONE,
            GLib.PRIORITY_LOW,
            cancellable);
    }
}

/**
 *
 * @param {Gtk.Window} window The X11 window
 */
function hideX11windowTaskbar(window) {
    window.connect('realize', w => {
        const gdkWindow = w.get_surface();
        gdkWindow.set_skip_pager_hint(true);
        gdkWindow.set_skip_taskbar_hint(true);
    });
}

/**
 *
 * @param {Gtk.Window} window The window
 * @param {boolean} modal If the window should by modal
 */
function windowHidePagerTaskbarModal(window, modal) {
    window.set_application(applicationid);
    let title = window.get_title();
    if (title === null)
        title = '';

    if (modal)
        title += '  ';
    else
        title += ' ';

    window.set_title(title);
    if (usingX11)
        hideX11windowTaskbar(window);

    if (modal) {
        window.set_modal(true);
        window.grab_focus();
    }
}

/**
 *
 * @param {integer} ms milliseconds
 */
function waitDelayMs(ms) {
    return new Promise(resolve => {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            resolve();
            return false;
        });
    });
}

/**
 * Coordiantes are the same
 *
 * @param {Array(integer)} coordA coordinates
 * @param {Array(integer)} coordB coordinates
 * @returns {boolean} true or false
 */
function coordinatesEqual(coordA, coordB) {
    if (coordA === coordB)
        return true;

    if (coordA && coordB)
        return (coordA[0] === coordB[0]) && (coordA[1] === coordB[1]);

    return false;
}
