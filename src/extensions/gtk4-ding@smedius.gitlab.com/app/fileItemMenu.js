/* DING: Desktop Icons New Generation for GNOME Shell
 *
 * Gtk4 Port Copyright (C) 2022 Sundeep Mediratta (smedius@gmail.com)
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

const { GLib, Gdk, Gtk, Gio } = imports.gi;

const TemplatesScriptsManager = imports.app.templatesScriptsManager;
const Prefs = imports.app.preferences;
const ShowErrorPopup = imports.app.showErrorPopup;
const DesktopIconsUtil = imports.utils.desktopIconsUtil;
const DBusUtils = imports.utils.dbusUtils;

const Gettext = imports.gettext.domain('gtk4-ding');

const _ = Gettext.gettext;

var FileItemMenu = class {
    constructor(desktopManager) {
        this._desktopManager = desktopManager;
        this._mainApp = this._desktopManager.mainApp;
        this._decompressibleTypes = [];
        DBusUtils.RemoteFileOperations.gnomeArchiveManager.connect('changed-status', (actor, available) => {
            if (available) {
                // wait a second to ensure that everything has settled
                GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
                    try {
                        this._getExtractionSupportedTypes();
                        return false;
                    } catch (e) {}
                });
            } else {
                this._decompressibleTypes = [];
            }
        });
        if (DBusUtils.RemoteFileOperations.gnomeArchiveManager.isAvailable)
            this._getExtractionSupportedTypes();


        this.scriptsMonitor = new TemplatesScriptsManager.TemplatesScriptsManager(
            DesktopIconsUtil.getScriptsDir(),
            this._onScriptClicked.bind(this),
            this._scriptsDirSelectionFilter.bind(this),
            this._desktopManager.mainApp,
            'scriptapp'
        );
        this.activeFileItem = null;
        this._createFileItemMenuActions();
    }

    _getExtractionSupportedTypes() {
        this._decompressibleTypes = [];
        const archiveProxy = DBusUtils.GnomeArchiveManager.proxy;
        try {
            archiveProxy?.GetSupportedTypesRemote('extract',
                (result, error) => {
                    if (error) {
                        print(`Can't get the extractable types: ${error.message}. Ensure that File-Roller is installed.\n${error}.`);
                        return;
                    }
                    for (let key of result.values()) {
                        for (let type of key.values())
                            this._decompressibleTypes.push(Object.values(type)[0]);
                    }
                }
            );
        } catch (e) {}
    }

    _scriptsDirSelectionFilter(fileinfo) {
        let name = fileinfo.get_name();
        let hidden = name.substring(0, 1) === '.';
        let executable = fileinfo.get_attribute_boolean('access::can-execute');
        if (!hidden && executable)
            return name;
        else
            return null;
    }

    _createFileItemMenuActions() {
        let openMultipleFileAction = Gio.SimpleAction.new('openMultipleFileAction', null);
        openMultipleFileAction.connect('activate', () => {
            this._doMultiOpen();
        });
        this._mainApp.add_action(openMultipleFileAction);

        let openOneFileAction = Gio.SimpleAction.new('openOneFileAction', null);
        openOneFileAction.connect('activate', () => {
            if (this.activeFileItem) {
                if (this.activeFileItem.isStackMarker)
                    this._desktopManager.onToggleStackUnstackThisTypeClicked(this.activeFileItem.attributeContentType);
                else
                    this.activeFileItem.doOpen();
            }
        });
        this._mainApp.add_action(openOneFileAction);
        this._mainApp.set_accels_for_action('app.openOneFileAction', ['Return']);

        let stackunstack = Gio.SimpleAction.new('stackunstack', GLib.VariantType.new('s'));
        stackunstack.connect('activate', (action, paramenter) => {
            this._desktopManager.onToggleStackUnstackThisTypeClicked(paramenter.unpack());
        });
        this._mainApp.add_action(stackunstack);

        let doopenwith = Gio.SimpleAction.new('doopenwith', null);
        doopenwith.connect('activate', this._doOpenWith.bind(this, null));
        this._mainApp.add_action(doopenwith);

        let graphicslaunch = Gio.SimpleAction.new('graphicslaunch', null);
        graphicslaunch.connect('activate', () => {
            this.activeFileItem.doDiscreteGpu();
        });
        this._mainApp.add_action(graphicslaunch);

        let runasaprogram = Gio.SimpleAction.new('runasaprogram', null);
        runasaprogram.connect('activate', () => {
            DesktopIconsUtil.spawnCommandLine(`"${this.activeFileItem.execLine}"`);
        });
        this._mainApp.add_action(runasaprogram);

        this._docut = Gio.SimpleAction.new('docut', null);
        this._docut.connect('activate', () => {
            this._desktopManager.doCut();
        });
        this._mainApp.add_action(this._docut);
        this._mainApp.set_accels_for_action('app.docut', ['<Control>X']);

        this._docopy = Gio.SimpleAction.new('docopy', null);
        this._docopy.connect('activate',  () => {
            this._desktopManager.doCopy();
        });
        this._mainApp.add_action(this._docopy);
        this._mainApp.set_accels_for_action('app.docopy', ['<Control>C']);

        let dorename = Gio.SimpleAction.new('dorename', null);
        dorename.connect('activate', () => {
            this._desktopManager.doRename(this.activeFileItem, false);
        });
        this._mainApp.add_action(dorename);
        this._mainApp.set_accels_for_action('app.dorename', ['F2']);

        this.moveToTrash = Gio.SimpleAction.new('movetotrash', null);
        this.moveToTrash.connect('activate', () => {
            this._desktopManager.doTrash();
        });
        this._mainApp.add_action(this.moveToTrash);
        this._mainApp.set_accels_for_action('app.movetotrash', ['Delete']);

        this.deletePermanantly = Gio.SimpleAction.new('deletepermanantly', null);
        this.deletePermanantly.connect('activate', () => {
            this._desktopManager.doDeletePermanently();
        });
        this._mainApp.add_action(this.deletePermanantly);
        this._mainApp.set_accels_for_action('app.deletepermanantly', ['<Shift>Delete']);

        let emptytrash = Gio.SimpleAction.new('emptytrash', null);
        emptytrash.connect('activate', () => {
            this._desktopManager.doEmptyTrash();
        });
        this._mainApp.add_action(emptytrash);

        let allowdisallowlaunching = Gio.SimpleAction.new('allowdisallowlaunching', null);
        allowdisallowlaunching.connect('activate', () => {
            this.activeFileItem.onAllowDisallowLaunchingClicked().catch(e => logError(e));
        });
        this._mainApp.add_action(allowdisallowlaunching);

        let eject = Gio.SimpleAction.new('eject', null);
        eject.connect('activate', () => {
            this.activeFileItem.eject().catch(e => logError(e));
        });
        this._mainApp.add_action(eject);

        let unmount = Gio.SimpleAction.new('unmount', null);
        unmount.connect('activate', () => {
            this.activeFileItem.unmount().catch(e => logError(e));
        });
        this._mainApp.add_action(unmount);

        let extractautoar = Gio.SimpleAction.new('extractautoar', null);
        extractautoar.connect('activate', () => this._desktopManager.getCurrentSelection(false).forEach(f =>
            this._desktopManager.autoAr.extractFile(f.fileName)));
        this._mainApp.add_action(extractautoar);

        let extracthere = Gio.SimpleAction.new('extracthere', null);
        extracthere.connect('activate', () => {
            this._extractFileFromSelection(true);
        });
        this._mainApp.add_action(extracthere);

        let extractto = Gio.SimpleAction.new('extractto', null);
        extractto.connect('activate', () => {
            this._extractFileFromSelection(false);
        });
        this._mainApp.add_action(extractto);

        let sendto = Gio.SimpleAction.new('sendto', null);
        sendto.connect('activate', this._mailFilesFromSelection.bind(this, null));
        this._mainApp.add_action(sendto);

        let compressfiles = Gio.SimpleAction.new('compressfiles', null);
        compressfiles.connect('activate', this._doCompressFilesFromSelection.bind(this, null));
        this._mainApp.add_action(compressfiles);

        let newfolderfromselection = Gio.SimpleAction.new('newfolderfromselection', null);
        newfolderfromselection.connect('activate', () => {
            const event = {
                'parentWindow': this.activeFileItem._grid._window,
                'timestamp': Gdk.CURRENT_TIME,
            };
            this._doNewFolderFromSelection(this.activeFileItem.savedCoordinates, this.activeFileItem, event).catch(e => logError(e));
        });
        this._mainApp.add_action(newfolderfromselection);

        let properties = Gio.SimpleAction.new('properties', null);
        properties.connect('activate', () => {
            this._onPropertiesClicked();
        });
        this._mainApp.add_action(properties);
        this._mainApp.set_accels_for_action('app.properties', ['<Control>I', '<Alt>Return']);

        let showinfiles = Gio.SimpleAction.new('showinfiles', null);
        showinfiles.connect('activate', this._onShowInFilesClicked.bind(this, null));
        this._mainApp.add_action(showinfiles);

        let openinterminal = Gio.SimpleAction.new('openinterminal', null);
        openinterminal.connect('activate', () => {
            DesktopIconsUtil.launchTerminal(this.activeFileItem.path, null);
        });
        this._mainApp.add_action(openinterminal);
    }

    showMenu(fileItem, button = null, X = null, Y = null, x = null, y = null, shiftSelected = false, controlSelected = false) {
        this.activeFileItem = this._desktopManager.activeFileItem = fileItem;
        const selectedItemsNum = this._desktopManager.getNumberOfSelectedItems();
        const scriptsSubmenu = this.scriptsMonitor.getGioMenu();
        const menulocation = X ? new Gdk.Rectangle({ x, y, width: 1, height: 1 }) : fileItem._grid.getGlobaltoLocalRectangle(fileItem.iconRectangle);

        this._menu = Gio.Menu.new();

        if (!this.activeFileItem.isStackMarker) {
            if (selectedItemsNum > 1)
                this._menu.append(_('Open All...'), 'app.openMultipleFileAction');
            else
                this._menu.append(_('Open'), 'app.openOneFileAction');
        }

        let keepStacked = Prefs.desktopSettings.get_boolean('keep-stacked');
        if (keepStacked && !fileItem.stackUnique) {
            if (!fileItem.isSpecial && !fileItem.isDirectory && !fileItem.isValidDesktopFile) {
                let unstackList = Prefs.getUnstackList();
                let typeInList = unstackList.includes(fileItem.attributeContentType);
                let menuitem = Gio.MenuItem.new(typeInList ? _('Stack This Type') : _('Unstack This Type'), null);
                let variant = GLib.Variant.new('s', fileItem.attributeContentType);
                menuitem.set_action_and_target_value('app.stackunstack', variant);
                this._menu.append_item(menuitem);
            }
        }

        // fileExtra == NONE

        if (fileItem.isAllSelectable &&  !fileItem.isStackMarker) {
            if (scriptsSubmenu !== null)
                this._menu.append_submenu(_('Scripts'), scriptsSubmenu);


            if (!fileItem.isDirectory) {
                let openWithMenu = Gio.Menu.new();
                openWithMenu.append(selectedItemsNum > 1 ? _('Open All With Other Application...') : _('Open With Other Application'), 'app.doopenwith');
                if (DBusUtils.discreteGpuAvailable && fileItem.trustedDesktopFile)
                    openWithMenu.append(_('Launch using Dedicated Graphics Card'), 'app.graphicslaunch');

                this._menu.append_section(null, openWithMenu);
            }

            if (fileItem.attributeCanExecute && !fileItem.isDirectory && !fileItem.isValidDesktopFile && fileItem.execLine && Gio.content_type_can_be_executable(fileItem.attributeContentType)) {
                let runAsProgram = Gio.Menu.new();
                runAsProgram.append(_('Run as a Program'), 'app.runasaprogram');
                this._menu.append_section(null, runAsProgram);
            }

            let allowCutCopyTrash = this._desktopManager.checkIfSpecialFilesAreSelected();
            let cutCopyPasteMenu = Gio.Menu.new();
            cutCopyPasteMenu.append(_('Cut'), 'app.docut');
            this._docut.set_enabled(!allowCutCopyTrash);
            cutCopyPasteMenu.append(_('Copy'), 'app.docopy');
            this._docopy.set_enabled(!allowCutCopyTrash);
            if (fileItem.canRename && (selectedItemsNum === 1))
                cutCopyPasteMenu.append(_('Rename…'), 'app.dorename');

            this._menu.append_section(null, cutCopyPasteMenu);

            let trashMenu = Gio.Menu.new();
            trashMenu.append(_('Move to Trash'), 'app.movetotrash');
            this.moveToTrash.set_enabled(!allowCutCopyTrash);
            if (Prefs.nautilusSettings.get_boolean('show-delete-permanently')) {
                trashMenu.append(_('Delete permanently'), 'app.deletepermanantly');
                this.deletePermanantly.set_enabled(!allowCutCopyTrash);
            }
            this._menu.append_section(null, trashMenu);

            if (fileItem.isValidDesktopFile && !this._desktopManager.writableByOthers && !fileItem.writableByOthers && (selectedItemsNum === 1)) {
                let allowLaunchingMenu = Gio.Menu.new();
                allowLaunchingMenu.append(fileItem.trustedDesktopFile ? _("Don't Allow Launching") : _('Allow Launching'), 'app.allowdisallowlaunching');
                this._menu.append_section(null, allowLaunchingMenu);
            }
        }

        // fileExtra == TRASH

        if (fileItem.isTrash) {
            let emptyTrashMenu = Gio.Menu.new();
            emptyTrashMenu.append(_('Empty Trash'), 'app.emptytrash');
            this._menu.append_section(null, emptyTrashMenu);
        }

        // fileExtra == EXTERNAL_DRIVE

        if (fileItem.isDrive) {
            let driveMenu = Gio.Menu.new();
            if (fileItem.canEject)
                driveMenu.append(_('Eject'), 'app.eject');

            if (fileItem.canUnmount)
                driveMenu.append(_('Unmount'), 'app.unmount');

            if (fileItem.canEject || fileItem.canUnmount)
                this._menu.append_section(null, driveMenu);
        }

        if (fileItem.isAllSelectable && !this._desktopManager.checkIfSpecialFilesAreSelected() && (selectedItemsNum >= 1)) {
            let extractMenu = Gio.Menu.new();
            let addedExtractHere = false;
            if (this._getExtractableAutoAr()) {
                addedExtractHere = true;
                extractMenu.append(_('Extract Here'), 'app.extractautoar');
            }
            if (selectedItemsNum === 1 && this._getExtractable()) {
                if (!addedExtractHere)
                    extractMenu.append(_('Extract Here'), 'app.extracthere');

                extractMenu.append(_('Extract To...'), 'app.extractto');
            }

            if (!fileItem.isDirectory)
                extractMenu.append(_('Send to...'), 'app.sendto');


            if (this._desktopManager.getCurrentSelection().every(f => f.isDirectory)) {
                extractMenu.append(
                    Gettext.ngettext(
                        'Compress {0} folder', 'Compress {0} folders', selectedItemsNum).replace(
                        '{0}', selectedItemsNum),
                    'app.compressfiles'
                );
            } else {
                extractMenu.append(
                    Gettext.ngettext(
                        'Compress {0} file', 'Compress {0} files', selectedItemsNum).replace(
                        '{0}', selectedItemsNum),
                    'app.compressfiles'
                );
            }

            extractMenu.append(
                Gettext.ngettext('New Folder with {0} item', 'New Folder with {0} items', selectedItemsNum).replace('{0}', selectedItemsNum),
                'app.newfolderfromselection'
            );

            this._menu.append_section(null, extractMenu);
        }

        if (!fileItem.isStackMarker) {
            let propertiesMenu = Gio.Menu.new();
            propertiesMenu.append(selectedItemsNum > 1 ? _('Common Properties') : _('Properties'), 'app.properties');
            this._menu.append_section(null, propertiesMenu);

            let showInFilesMenu = Gio.Menu.new();
            showInFilesMenu.append(selectedItemsNum > 1 ? _('Show All in Files') : _('Show in Files'), 'app.showinfiles');
            this._menu.append_section(null, showInFilesMenu);
        }

        if (fileItem.isDirectory && (fileItem.path !== null) && (selectedItemsNum === 1)) {
            let openInTerminalMenu = Gio.Menu.new();
            openInTerminalMenu.append(_('Open in Terminal'), 'app.openinterminal');
            this._menu.append_section(null, openInTerminalMenu);
        }
        this.popupmenu = Gtk.PopoverMenu.new_from_model(this._menu);
        this.popupmenu.set_parent(fileItem._grid._container);
        this.popupmenu.set_pointing_to(menulocation);
        const menuGtkPosition = fileItem._grid.getIntelligentPosition(menulocation);
        if (menuGtkPosition)
            this.popupmenu.set_position(menuGtkPosition);

        fileItem._desktopManager.popupmenuopen = this.popupmenuopen = true;
        this.popupmenu.popup();
        this.popupmenu.connect('closed', async () => {
            this._desktopManager.popupmenuopen = this.popupmenuopen = false;
            fileItem._grid.enableIntellihide();
            await DesktopIconsUtil.waitDelayMs(50);
            this.popupmenu.unparent();
        });
    }

    _onPropertiesClicked() {
        let propertiesFileList = this._desktopManager.getCurrentSelection(true);
        const timestamp = Gdk.CURRENT_TIME;
        DBusUtils.RemoteFileOperations.ShowItemPropertiesRemote(propertiesFileList, timestamp);
    }

    _onShowInFilesClicked() {
        let showInFilesList = this._desktopManager.getCurrentSelection(true);
        if (this._desktopManager.useNemo) {
            try {
                for (let element of showInFilesList)
                    DesktopIconsUtil.trySpawn(GLib.get_home_dir(), ['nemo', element], DesktopIconsUtil.getFilteredEnviron());

                return;
            } catch (err) {
                log(`Error trying to launch Nemo: ${err.message}\n${err}`);
            }
        }
        const timestamp = Gdk.CURRENT_TIME;
        DBusUtils.RemoteFileOperations.ShowItemsRemote(showInFilesList, timestamp);
    }

    _doMultiOpen() {
        for (let fileItem of this._desktopManager.getCurrentSelection(false)) {
            fileItem.unsetSelected();
            fileItem.doOpen();
        }
    }

    _doOpenWith() {
        let fileItems = this._desktopManager.getCurrentSelection(false);
        if (fileItems) {
            const context = Gdk.Display.get_default().get_app_launch_context();
            context.set_timestamp(Gdk.CURRENT_TIME);
            let mimetype = Gio.content_type_guess(fileItems[0].fileName, null)[0];
            let chooser = Gtk.AppChooserDialog.new_for_content_type(null,
                Gtk.DialogFlags.MODAL + Gtk.DialogFlags.USE_HEADER_BAR,
                mimetype);
            this._desktopManager.textEntryAccelsTurnOff();
            chooser.show();
            chooser.present_with_time(Gdk.CURRENT_TIME);
            chooser.connect('close', () => {
                chooser.response(Gtk.ResponseType.CANCEL);
            });
            chooser.connect('response', (actor, retval) => {
                if (retval === Gtk.ResponseType.OK) {
                    let appInfo = chooser.get_app_info();
                    if (appInfo) {
                        let fileList = [];
                        for (let item of fileItems)
                            fileList.push(item.file);

                        appInfo.launch(fileList, context);
                    }
                }
                this._desktopManager.textEntryAccelsTurnOn();
                chooser.hide();
                chooser.destroy();
            });
        }
    }

    async _extractFileFromSelection(extractHere) {
        let extractFileItemURI;
        let extractFolderName;
        let position;
        const header = _('No Extraction Folder');
        const text = _('Unable to extract File, extraction Folder Does not Exist');

        for (let fileItem of this._desktopManager.getCurrentSelection(false)) {
            extractFileItemURI = fileItem.file.get_uri();
            extractFolderName = fileItem.fileName;
            position = fileItem.getCoordinates().slice(0, 2);
            fileItem.unsetSelected();
        }

        if (extractHere) {
            extractFolderName = DesktopIconsUtil.getFileExtensionOffset(extractFolderName).basename;
            const targetURI = await this._desktopManager.doNewFolder(position, extractFolderName, { rename: false });
            if (targetURI)
                DBusUtils.RemoteFileOperations.ExtractRemote(extractFileItemURI, targetURI, true);
            else
                this._desktopManager.DBusManager.doNotify(header, text);

            return;
        }

        const dialog = new Gtk.FileChooserDialog({ title: _('Select Extract Destination') });
        dialog.set_action(Gtk.FileChooserAction.SELECT_FOLDER);
        dialog.set_create_folders(true);
        dialog.set_current_folder(DesktopIconsUtil.getDesktopDir());
        dialog.add_button(_('Cancel'), Gtk.ResponseType.CANCEL);
        dialog.add_button(_('Select'), Gtk.ResponseType.ACCEPT);
        DesktopIconsUtil.windowHidePagerTaskbarModal(dialog, true);
        this._desktopManager.textEntryAccelsTurnOff();
        dialog.show();
        dialog.present_with_time(Gdk.CURRENT_TIME);
        dialog.connect('close', () => {
            dialog.response(Gtk.ResponseType.CANCEL);
        });
        dialog.connect('response', (actor, response) => {
            if (response === Gtk.ResponseType.ACCEPT) {
                const folder = dialog.get_file().get_uri();
                if (folder)
                    DBusUtils.RemoteFileOperations.ExtractRemote(extractFileItemURI, folder, true);
                else
                    this._desktopManager.DBusManager.doNotify(header, text);
            }
            this._desktopManager.textEntryAccelsTurnOn();
            dialog.destroy();
        });
    }

    _getExtractableAutoAr() {
        let fileList = this._desktopManager.getCurrentSelection(false);
        if (DBusUtils.GnomeArchiveManager.isAvailable && (fileList.length === 1))
            return false;

        for (let item of fileList) {
            if (!this._desktopManager.autoAr.fileIsCompressed(item.fileName))
                return false;
        }
        return true;
    }

    _getExtractable() {
        for (let item of this._desktopManager.getCurrentSelection(false))
            return this._decompressibleTypes.includes(item.attributeContentType);
    }

    _mailFilesFromSelection() {
        if (this._desktopManager.checkIfDirectoryIsSelected()) {
            let WindowError = new ShowErrorPopup.ShowErrorPopup(_('Can not email a Directory'),
                _('Selection includes a Directory, compress the directory to a file first.'),
                false,
                this._textEntryAccelsTurnOff.bind(this),
                this._textEntryAccelsTurnOn.bind(this));
            WindowError.run();
            return;
        }
        let xdgEmailCommand = [];
        xdgEmailCommand.push('xdg-email');
        for (let fileItem of this._desktopManager.getCurrentSelection(false)) {
            fileItem.unsetSelected;
            xdgEmailCommand.push('--attach');
            xdgEmailCommand.push(fileItem.file.get_path());
        }
        DesktopIconsUtil.trySpawn(null, xdgEmailCommand);
    }

    _doCompressFilesFromSelection() {
        let desktopFolder = DesktopIconsUtil.getDesktopDir();
        if (desktopFolder) {
            if (DBusUtils.GnomeArchiveManager.isAvailable) {
                const toCompress = this._desktopManager.getCurrentSelection(true);
                DBusUtils.RemoteFileOperations.CompressRemote(toCompress, desktopFolder.get_uri(), true);
            } else {
                const toCompress = this._desktopManager.getCurrentSelection(false);
                this._desktopManager.autoAr.compressFileItems(toCompress, desktopFolder.get_path());
            }
        }
        this._desktopManager.unselectAll();
    }

    async _doNewFolderFromSelection(assignedposition = null, clickedItem, event) {
        if (!clickedItem)
            return;

        let position = assignedposition ? assignedposition  : clickedItem.savedCoordinates;
        let newFolderFileItems = this._desktopManager.getCurrentSelection(true);
        this._desktopManager.unselectAll();
        clickedItem.removeFromGrid({ callOnDestroy: false });
        const newFolder = await this._desktopManager.doNewFolder(position);
        if (newFolder) {
            DBusUtils.RemoteFileOperations.pushEvent(event);
            DBusUtils.RemoteFileOperations.MoveURIsRemote(newFolderFileItems, newFolder);
        }
    }

    _onScriptClicked(menuItemPath) {
        let pathList = 'NAUTILUS_SCRIPT_SELECTED_FILE_PATHS=';
        let uriList = 'NAUTILUS_SCRIPT_SELECTED_URIS=';
        let currentUri = `NAUTILUS_SCRIPT_CURRENT_URI=${DesktopIconsUtil.getDesktopDir().get_uri()}`;
        let params = [menuItemPath];
        for (let item of this._desktopManager.getCurrentSelection(false)) {
            if (!item.isSpecial) {
                pathList += `${item.file.get_path()}\n`;
                uriList += `${item.file.get_uri()}\n`;
                params.push(item.file.get_path());
            }
        }

        let environ = DesktopIconsUtil.getFilteredEnviron();
        environ.push(pathList);
        environ.push(uriList);
        environ.push(currentUri);
        DesktopIconsUtil.trySpawn(null, params, environ);
    }

    _textEntryAccelsTurnOff() {
        this._desktopManager.textEntryAccelsTurnOff();
    }

    _textEntryAccelsTurnOn() {
        this._desktopManager.textEntryAccelsTurnOn();
    }
};
