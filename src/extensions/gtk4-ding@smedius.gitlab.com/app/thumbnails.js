/* DING: Desktop Icons New Generation for GNOME Shell
 *
 * Copyright (C) 2022 Sundeep Mediratta (smedius@gmail.com) port to work with
 * gnome desktop 3 or 4 so as to communicate over dbus.
 *
 * Code cherry picked from Marco Trevisan for async methods to generate icons.
 *
 * Copyright (C) 2021 Sergio Costas (rastersoft@gmail.com)
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

var gnomedesktop;
var Gtk;
var GnomeDesktop;

try {
    imports.gi.versions.GnomeDesktop = '4.0';
    imports.gi.versions.Gtk = '4.0';
    gnomedesktop = 4;
    Gtk = imports.gi.Gtk;
    GnomeDesktop = imports.gi.GnomeDesktop;
} catch (e) {
    gnomedesktop = 3;
    imports.gi.versions.GnomeDesktop = '3.0';
    imports.gi.versions.Gtk = '3.0';
    Gtk = imports.gi.Gtk;
    GnomeDesktop = imports.gi.GnomeDesktop;
}

const { GLib, Gio } = imports.gi;
const FileUtils = imports.utils.fileUtils;

const useAsyncAPI =
    !!GnomeDesktop.DesktopThumbnailFactory.prototype.generate_thumbnail_async;

if (useAsyncAPI) {
    Gio._promisify(GnomeDesktop.DesktopThumbnailFactory.prototype,
        'generate_thumbnail_async',
        'generate_thumbnail_finish');
    Gio._promisify(GnomeDesktop.DesktopThumbnailFactory.prototype,
        'create_failed_thumbnail_async',
        'create_failed_thumbnail_finish');
    Gio._promisify(GnomeDesktop.DesktopThumbnailFactory.prototype,
        'save_thumbnail_async',
        'save_thumbnail_finish');
}

var ThumbnailLoader = class {
    constructor(codePath) {
        this._timeoutValue = 5000;
        this._codePath = codePath;
        this._thumbnailFactory = GnomeDesktop.DesktopThumbnailFactory.new(GnomeDesktop.DesktopThumbnailSize.LARGE);
        if (useAsyncAPI)
            print('Detected async api for thumbnails');
        else
            print('Failed to detected async api for thumbnails');
    }

    async _generateThumbnail(file, cancellable) {
        if (!await FileUtils.queryExists(file.file))
            return null;

        if (this._thumbnailFactory.has_valid_failed_thumbnail(file.uri, file.modifiedTime))
            return null;

        if (useAsyncAPI) {
            if (!await this._createThumbnailAsync(file, cancellable))
                return null;
        } else if (!await this._createThumbnailSubprocess(file, cancellable)) {
            return null;
        }

        if (cancellable.is_cancelled())
            return null;

        return this._thumbnailFactory.lookup(file.uri, file.modifiedTime);
    }

    async _createThumbnailAsync(file, cancellable) {
        let gotTimeout = false;
        let timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, this._timeoutValue, () => {
            print(`Timeout while generating thumbnail for ${file.displayName}`);
            timeoutId = 0;
            gotTimeout = true;
            cancellable.cancel();
            return GLib.SOURCE_REMOVE;
        });

        let modifiedTime;
        let fileInfo;
        try {
            fileInfo = await file.file.query_info_async('standard::content-type,time::modified',
                Gio.FileQueryInfoFlags.NONE, GLib.PRIORITY_DEFAULT, cancellable);
            modifiedTime = fileInfo.get_attribute_uint64('time::modified');
        } catch (e) {
            if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                logError(e, `Error while creating thumbnail: ${e.message}`);
            return false;
        }

        try {
            const thumbnailPixbuf = await this._thumbnailFactory.generate_thumbnail_async(
                file.uri, fileInfo.get_content_type(), cancellable);
            await this._thumbnailFactory.save_thumbnail_async(thumbnailPixbuf,
                file.uri, modifiedTime, cancellable);
            return true;
        } catch (e) {
            if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                logError(e, `Error while creating thumbnail: ${e.message}`);
            await this._createFailedThumbnailAsync(file, modifiedTime,
                gotTimeout && cancellable.is_cancelled() ? null : cancellable);
        } finally {
            if (timeoutId)
                GLib.source_remove(timeoutId);
        }

        return false;
    }

    async _createFailedThumbnailAsync(file, modifiedTime, cancellable) {
        try {
            await this._thumbnailFactory.create_failed_thumbnail_async(file.uri,
                modifiedTime, cancellable);
        } catch (e) {
            logError(e, `Error while creating failed thumbnail: ${e.message}`);
        }
    }

    async _createThumbnailSubprocess(file, cancellable) {
        const args = [];
        args.push(GLib.build_filenamev([this._codePath, 'createThumbnail.js']));
        args.push(file.path);
        const proc = new Gio.Subprocess({ argv: args });

        let timeoutID = GLib.timeout_add(GLib.PRIORITY_DEFAULT, this._timeoutValue, () => {
            print(`Timeout while generating thumbnail for ${file.displayName}`);
            timeoutID = 0;
            proc.force_exit();
            this._thumbnailFactory.create_failed_thumbnail(file.uri, file.modifiedTime);
            return GLib.SOURCE_REMOVE;
        });

        proc.init(null);

        try {
            await proc.wait_check_async(cancellable);
            return proc.get_status() === 0;
        } catch (e) {
            if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                logError(e, `Failed to generate thumbnail for ${file.displayName}: ${e.message}`);
        } finally {
            if (timeoutID)
                GLib.source_remove(timeoutID);
        }

        return false;
    }

    canThumbnail(file) {
        return this._thumbnailFactory.can_thumbnail(file.uri,
            file.attributeContentType,
            file.modifiedTime);
    }

    async getThumbnail(file, cancellable) {
        try {
            let thumbnail = this._thumbnailFactory.lookup(file.uri, file.modifiedTime);
            if (thumbnail === null)
                thumbnail = await this._generateThumbnail(file, cancellable);

            return thumbnail;
        } catch (error) {
            print(`Error when asking for a thumbnail for ${file.displayName}: ${error.message}\n${error.stack}`);
        }
        return null;
    }
};
