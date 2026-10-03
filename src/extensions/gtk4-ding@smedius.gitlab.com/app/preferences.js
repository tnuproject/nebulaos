/* DING: Desktop Icons New Generation for GNOME Shell
 *
 * Gtk4 Port Copyright (C) 2022 Sundeep Mediratta (smedius@gmail.com)
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

imports.gi.versions.Gtk = '4.0';

const { GLib, Gtk, GObject, Gio } = imports.gi;
const GioSSS = Gio.SettingsSchemaSource;
const PrefrencesFrame = imports.app.preferencesFrame;

const Gettext = imports.gettext;

var _ = Gettext.domain('gtk4-ding').gettext;

var extensionPath;
var Enums;

var nautilusSettings;
var nautilusCompression;
var gtkSettings;
var desktopSettings;
// This is already in Nautilus settings, so it should not be made tweakable here
var CLICK_POLICY_SINGLE = false;
var preferencesFrame;

/**
 *
 * @param path
 * @param enums
 */
function init(path, enums) {
    extensionPath = path;
    Enums = enums;
    let schemaSource = GioSSS.get_default();
    let schemaGtk = schemaSource.lookup(Enums.SCHEMA_GTK, true);
    gtkSettings = new Gio.Settings({ settings_schema: schemaGtk });
    let schemaObj = schemaSource.lookup(Enums.SCHEMA_NAUTILUS, true);
    if (!schemaObj) {
        nautilusSettings = null;
    } else {
        nautilusSettings = new Gio.Settings({ settings_schema: schemaObj });
        nautilusSettings.connect('changed', _onNautilusSettingsChanged);
        _onNautilusSettingsChanged();
    }
    const compressionSchema = schemaSource.lookup(Enums.SCHEMA_NAUTILUS_COMPRESSION, true);
    if (!compressionSchema)
        nautilusCompression = null;
    else
        nautilusCompression = new Gio.Settings({ settings_schema: compressionSchema });

    desktopSettings = get_schema(Enums.SCHEMA);

    preferencesFrame = new PrefrencesFrame.PreferencesFrame(Gtk, GObject, desktopSettings, nautilusSettings, gtkSettings, _);
}

/**
 *
 * @param schema
 */
function get_schema(schema) {
    // check if this extension was built with "make zip-file", and thus
    // has the schema files in a subfolder
    // otherwise assume that extension has been installed in the
    // same prefix as gnome-shell (and therefore schemas are available
    // in the standard folders)
    let schemaSource;
    let schemaFile = Gio.File.new_for_path(GLib.build_filenamev([extensionPath, 'schemas', 'gschemas.compiled']));
    if (schemaFile.query_exists(null))
        schemaSource = GioSSS.new_from_directory(GLib.build_filenamev([extensionPath, 'schemas']), GioSSS.get_default(), false);
    else
        schemaSource = GioSSS.get_default();


    let schemaObj = schemaSource.lookup(schema, true);
    if (!schemaObj)
        throw new Error(`Schema ${schema} could not be found for extension. Please check your installation.`);

    return new Gio.Settings({ settings_schema: schemaObj });
}

function get_preferencesFrame() {
    return preferencesFrame.getFrame();
}

/**
 *
 */
function _onNautilusSettingsChanged() {
    CLICK_POLICY_SINGLE = nautilusSettings.get_string('click-policy') === 'single';
}

/**
 *
 */
function get_icon_size() {
    return Enums.ICON_SIZE[desktopSettings.get_string('icon-size')];
}

/**
 *
 */
function get_desired_width() {
    return Enums.ICON_WIDTH[desktopSettings.get_string('icon-size')];
}

/**
 *
 */
function get_desired_height() {
    return Enums.ICON_HEIGHT[desktopSettings.get_string('icon-size')];
}

/**
 *
 */
function get_start_corner() {
    return Enums.START_CORNER[desktopSettings.get_string('start-corner')].slice();
}

/**
 *
 */
function getSortOrder() {
    return Enums.SortOrder[desktopSettings.get_string(Enums.SortOrder.ORDER)];
}

/**
 *
 * @param order
 */
function setSortOrder(order) {
    let x = Object.values(Enums.SortOrder).indexOf(order);
    desktopSettings.set_enum(Enums.SortOrder.ORDER, x);
}

/**
 *
 */
function getUnstackList() {
    return desktopSettings.get_strv('unstackedtypes');
}

/**
 *
 * @param array
 */
function setUnstackList(array) {
    desktopSettings.set_strv('unstackedtypes', array);
}
