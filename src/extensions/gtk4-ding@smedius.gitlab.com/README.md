# Gtk4 DING Desktop Icons New Generation

## What is it?

Gtk4 Desktop Icons NG is an extension and a program together for the GNOME Shell that renders icons on the desktop. It is a fork from DING.

Desktop Icons NG (DING) by Sergio Costas itself is a fork/rewrite of the official 'Desktop Icons' extension, orignially by Carlos Soriano.

This new Gtk4 extension is also submitted upstream to the DING project as a merge request. It has not been merged yet. Therefore there are two extensions available, the classic stable Gtk3 DING and this newer, less tested Gtk4 branch.

This fork of DING is ported to use the Gtk4 toolkit. This, and the original DING can both be installed together, but only one can be activated at a time in the extension Manager. They use different install directories and GSettings schemas, therefore preferences set in one will not carrry through to the other. This is to avoid trampling on the stable branch and isolate errors from this branch.

Other than using the Gtk4 toolkit, it in addition it has several new features, fixes and enhancemnts.

**NEW FEATURES**

- [x] Can Make Links on the Desktop on Drag and Drop from Nautilus. Pressing the Alt button on drag modifies the drop to ask the user to Copy, Move or Make Links at the destination.

- [x] Links are checked just before launching them, in case they got broken in the background with no recent desktop refresh. If they are broken the icon is updated to the broken link icon, and the error dialog is popped up correctly. The reverse is also true, if a broken link resolves correctly as the target re-appeared, the link is opened and the icon updated to the correct icon.

- [x] Copied files retain the dropped position.

- [x] Merged all changes from branch more-asyncness, by Marco Trevisan, that was submitted upstream, to this Gtk4 branch to use async functions for everything.

- [x] Make DBus Proxies asynchronously, so the extension starts at once and does not hang till DBus services respond to requests.

- [x] Prevent Flashing Icons - Use async await promises to update the entire fileList icon widgets prior to placing on desktop. Do the same for stack Top Marker Folders.

- [x] Use Promises to detect when icons have been placed on the desktop, so that in draw desktop, it is clear that all the icons are placed on the desktop and desktop drawing is complete. This allows queuing code that can only be executed when icon placing is complete and the desktop draw is done.

- [x] Optimize refreshMenus after Icons are placed on Grid to point to the correct fileItem with the above promise. Also remake the menu as the old menu does not scroll and malfunctions. Same for do rename popup. No longer uses callback from fileItem to call these functions. Directly use Promises made above to update the menus and rename popups after icons are placed on grid. Stack top marker menus are also repositioned.

- [x] When Dock in in intelligent hide or auto hide mode, all menus and rename popups can be popped up under the dock, the dock does not detect them as it ignores DING completely. Updated the code to detect dock or any other object is likely in auto hide mode by detecting usableArea margins are set. Then popups the menu in the correct position so that they do not go under the dock or other auto hide object on the desktop.

- [x] Add eslintrc.json file and lint folder containing eslint rules for GJS/Gnome files eslintrc-gjs.yml and eslintrc-shell.yml for linting.

- [x] The entire project and all .js files are now scanned and corrected with eslint. All formatting is fixed and errors from eslint resolved, should follow GJS/Gnome guidelines.

- [x] Other than the UUID of the extension, changed the application ID, the Dbus object paths and GSetting schemas for the application. This is to differentiate it from the gtk-3 desktop icons NG extension. Both can be installed simultaneously on the same system. However both should not be run at the same time, only one extension should be active. This lets users test the extension, report problems that need fixing, and revert to the original gtk3 DING if does not work for them.

- [x] For Gnome 42, allow use of 'unlock-dialog' in session mode for the extension, so that it is not relaunched every time.

- [x] Re-organization, New Folder structure to avoid confusion and facilitate review.

- [x] Update to work with Gnome 43 and Nautilus 43rc. Drag and drop with Gnome 43 more reliable using Gdk.FileList

- [x] More Reliable parsing of string URI lists with old Nautilus with GLib.Uri.

- [x] Give visual feedback and prevent smoothly dropping special files if selected, on Nautilus windows by doing local drops by accepting but not reading drop data.

- [x] Use native TextEncoder and TextDecoder objects in GJS instead of ByteArray imports.

**EXPERIMENTAL FEATURES**

There is optional integration with Gsconnect extension available. If Gsconnect extension is installed, right click menus allow sending files directly from the desktop using Gsconnect. To use this feature, look for the "Gtk4-gsconnect-integration" branch in this repository, and install from that branch. Feedback, fixes appreciated, this branch has not been well tested at all.


**FIXES**

- [x] Fix Gtk4 Icon Rendering Code to at least render generic correct icons at the correct size.

- [x] Fix Drag and Drop. Need to add drag and drop controllers to DesktipIconItem.js.

- [x] Fix Rectangle Selection in Gtk4. Fixed by using Gtk.Overlay.

- [x] Fix clipboard. Fixed. Use new Gdk4 clipboard object, remove old dbus code and St. library clipboard code from extension.js

- [x] Fix DbusUtils Nautilus Wayland window handle. Can successfully get Wayland window handle via asynchronous call, using a promise with Gtk4. This is passed to Nautilus. Reset on callback from the Dbus call.

- [x] Cosmetic Fixes to Boxes as Padding and spacing is gone in Gtk4 and need to use other methods.

- [x] Composite Emblem Icons using Gtk4

- [x] Set custom icons using Gtk4 methods and calls.

- [x] Make Gtk4 Icons skinny, not tiles so that there is space around them to initiate selection rectangles.

- [x] Use Gtk Application keyboard accelerators for functions, Shortcuts are shown in Gio.Menus.

- [x] All menus are Gio.Menus.

- [x] Thumbnail.js GnomeDesktop.DesktopThumbnailFactory is Gtk3, will not work with current code. Till that is ported, thumbnail.js is launched as a separate Gtk Application, ding and thumbnail.js exchange thumbnail information over dbus. This is the last thing to complete this port. This is done for Gnome 40, Gnome 41.

- [x] GnomeDesktop4 is now available in some distros on Gnome 41. Others have it in Gnome 42 (eg Ubuntu Jammy). This branch now checks to see which version is available. If GnomeDesktop4 is available, it uses it directly to render thumbnails. If not available, it launches a helper app that uses Gtk3 and GnomeDesktop3, communicates with it over Dbus to render thumbnails.

- [x] Fix - the desktop is not highlighted with a green rectangle on Drag and Drop.

- [x] Fix - Rename popups and fileItem right click menus work correctly even if the desktop is refreshed while they are open. Rename popups and the right click menus are re positioned to point to the correct fileItem and both menus always operate on the correct file/fileItem. This also applies to stacktopItems, if they move the right click menu updates and moves with them.

- [x] Fix - Selection is kept even if the desktop is refreshed.

- [x] Fix - Keyboard accelerators work even after Gtk.PopoverMenu sub-menus are shown and dismissed. This seems to be a bug in Gtk4, accelerators don't work after a submenu is shown and dismissed, the fix is a little bit of a kludge, but gets the job done till this is fixed upstream.

- [x] Fix - Window Transparency under X11.

- [x] Gtk4 does not allow window move even on X11. X11 windows are now managed by the extension in the same way as Wayland windows.

- [x] Leverages Gtk4 calls to translate coordinates. Fix Rubber band initiation by correcting the grid Global Rectangle, local to global and global to local coordinates. Leverages Gtk calls for \_coordinatesBelongToThisGrid() and new \_coordinatesBelongToThisWindow(); Fixes initiation of this.globalRectangle using the above calls. Fixes iconContainer and labelContainer global rectangles with the above calls as well so that they work with fractional scaling. Thanks to Sergio Costas for Pointing out that eventbox gives negative coordinates in margins. Fix for correcting getDistance(x, y) from Sergio Costas !348. Removed scale from desktopgrid.js. Removed zoom from desktopIconItem.js

- [x] Refactoring to avoid boolean parameters, make code more readable. Added eslint.json and GJS/Gnome eslintrc-gjs.yml and eslintrc-shell.yml for linting.


**KNOWN ISSUES**

- [ ] On X11, in latest Ubuntu and Fedora, Gtk.GestureClick.get_current_event_state() button click returns wrong state, crashing the Program. Works perfectly on Wayland on all distributions tried, works even on X11 on Manjaro and by extension on likely Arch Linux as well. Likely problem in GJS. Reported upstream [here](https://discourse.gnome.org/t/gtk4-eventcontroller-gestureclick-returns-incorrect-state-gdk-modifiertype-on-mouse-button-press-in-x11/9710) in Gnome Discourse and [here](https://bugs.launchpad.net/ubuntu/+source/gjs/+bug/1975544) on Ubuntu Launchpad.

- [ ] Gdk.Display.get_default().get_app_launch_context() when used in launch() to launch a desktop file crashes GJS. Likely problem in GJS. Current workaround is not to use the context, set to null, till fixed upstream.

- [ ] Dragged Icon sets the wrong offset for the cursor and defaults to 0,0 with Gtk.DragSource.set_icon in Wayland. This works perfectly in X11 and the correct offset is set. Again problem in Gtk4 on Wayland, But reported and issue in Gtk4 [here](https://gitlab.gnome.org/GNOME/gtk/-/issues/2341), however drag and drop otherwise works perfectly till fixed upstream.

- [ ] Application keyboard shortcut accelerators stop working after a submenu of a menu is closed, work perfectly if only the menu is closed. Bug reported [here](https://discourse.gnome.org/t/gtk4-eventcontroller-gestureclick-returns-incorrect-state-gdk-modifiertype-on-mouse-button-press-in-x11/9710) in Gnome Discourse, no clear solution. Current workaround is to destroy the menu once closed. Keyboard accelerators then work again normally.

- [ ] Nesting submenus do not work, crash GJS, currently use sliding submenus with Gio.Menu. Bug reported [here](https://discourse.gnome.org/t/gtk4-gtk-popovermenu-new-from-model-full-fails-in-gjs/9603) in Gnome Discourse, and [fix](https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/4668) was committed upstream. Wait till widely available in distributions prior to using option for nesting submenus, currently use sliding submenus.

- [ ] Gtk.DropTargetAsync(), in X11, does not set Gtk.StateFlags.NORMAL on the widget once the drag is finished. Current workaround is to set it manually with Widget.set_state_flags(Gtk.StateFlags.NORMAL, true) explicitly on drag end. It works perfectly on Wayland without a workaround.

If this extension does not work for you, just deactivate it in extensions manager, and you can use the classic DING Gtk3 extension.

Please report errors, and if you can fix it, please do so. See Contributing below.

## Requirements

* GNOME Shell >= 40
* Nautilus >= 3.38
* File-roller >= 3.38 or Gnome AutoAr (including gir1.2 files)
* Desktop folder already created

## Manual installation

The easiest way of installing DING is to run the `scripts/local_install.sh` script from the source directory (after changing directory to the source directory). The script assumes that it is being called from the base of the source directory. It performs the build steps specified in the next section.

In Ubuntu Jammy and probably later, the Ubuntu session is locked and only the default Ubuntu extensions run. Ubuntu runs it's own Desktop Icon Extension. Therefore, installing the extension from extensions.gnome.org will not work directly. The install script provided in the repository bypasses this and installs this as a manually installed extension. The default Desktop Icons extension that ships with Ubuntu then needs to be deactivated, and the manually installed one activated.

The other way to update to the newest one in Ubuntu is to install the "gnome-session" package, to enable the use of a standard gnome shell session, and in that session install the following extensions from extensions.gnome.org:

* This Extension
* Dash to dock
* Appindicator and KstatusNotifierItem support

That will allow the experience similar to the original Ubuntu desktop, but with the most recent versions of the extensions, without the default Ubuntu Desktop Icons Extension.

## Internal architecture

The code is divided in two parts: a classic Gtk4 program that manages the whole desktop, and a little extension (comprised only by the files 'extension.js', 'gnomeShellOverride.js', 'visibleArea.js' and 'emulateX11WindowType.js') that have these roles:

* Launch the desktop program at startup, relaunch it if it dies, and kill it if the extension is disabled
* Identify the desktop windows and keep it at the bottom of the windows stack, in all desktops
* Detect changes in the desktop/monitors geometry and notify the main desktop program of them

These two last items are paramount in Wayland systems, because there an application can neither set its role as freely as in X11, nor get that information.

Of course, to avoid breaking the security model of Wayland, it is paramount to ensure that no other program can pose as DING. In old versions, the process for identifying the window was quite convoluted, passing an UUID through STDIN and putting it in the window title. But since Gnome Shell 3.38 there is a new API that allows to check whether a window belongs to an specific process launched from an extension, which makes the code much cleaner and straightforward.

The extension monitors all 'map' signals, and when a window from the DING process previously launched is mapped, it knows that it is the desktop window. It stores that window object, sends it to the bottom of the stack, and connects to three signals:

* raised: it is called every time the window is sent to the front, so in the callback, the extension sends it again to the bottom.
* position-changed: although the window doesn't have titlebar, it still is possible to move it using Alt+F7, or pressing Super and dragging it with the mouse, so this callback returns the window to the right possition every time the user tries to move it.
* unmanaged: called when the window disappears. It deletes the UUID, and waits for the desktop program to be killed (it will be relaunched again by the extension, and, of course, a new UUID will be used).

It also monitors other signals to ensure that the desktop receives the focus only when there are no other windows in the current desktop, and to keep the icons in the right screen, no matter if the user changes to another virtual desktop.

The extension also intercepts three Gnome Shell system calls, in order to hide the desktop windows from the tab switcher and the Activities mode. These are  Meta.Display.get_tab_list()', 'Shell.Global.get_window_actors()', and 'Meta.Workspace.list_windows()'.

## Launching the Desktop Icons application stand-alone

It is possible to launch the desktop icons application in stand-alone mode to do debugging and testing, but, of course, it will behave as a classic Gtk program: there will be a window with its titlebar, and the background won't be transparent (it could be, but since the idea is to do debug, it is better this way). To do so, just launch 'app/ding.js' from the base repository directory. If it can't find the schemas file, just enter the 'schemas' folder and type 'glib-compile-schemas .', and retry.

It accepts the following command line parameters:

* -P: specifies the working path. If not set, it will default to './', which means that all the other
files must be in the current path.
* -D: specifies a monitor. It is followed by another parameter in the form: X:Y:W:H:Z being each letter
      a number with, respectively:
  * X: the X coordinate of this monitor
  * Y: the Y coordinate of this monitor
  * W: the width in pixels of this monitor
  * H: the height in pixels of this monitor
  * Z: the zoom value for this monitor
  you can set several -D parameters in the same command line, one for each monitor. A single window
  will be created for each monitor. If no -D parameter is specified, it will create a single monitor
  with a size of 1280x720 pixels.
* -M: specifies which monitor is the primary index, to add there any new file icon.

## Build with Meson

The project uses a build system called [Meson](https://mesonbuild.com/). You can install in most Linux distributions as "meson". You also need "ninja" and xgettext.

It's possible to read more information in the Meson docs to tweak the configuration if needed.

For a regular use and local development these are the steps to build the project and install it:

```bash
cp /scripts/meson.build ./
meson --prefix=$HOME/.local/ --localedir=share/gnome-shell/extensions/gtk4-ding@smedius.gilab.com/locale .build
ninja -C .build install
```

It is strongly recommended to delete the destination folder ($HOME/.local/share/gnome-shell/extensions/gt4-ding@smedius.gitlab.com) before doing this, to ensure that no old
data is kept. It is also recommended to delete the local .build folder and the copied file meson.build after the build is finished to clean up.

## Installing with Puppet

If you want to install it in several machines using puppet, you must first create an installation folder in your local machine using:

```bash
mkdir install_folder
cp scripts/meson.build ./
meson --prefix=`pwd`/install_folder --localedir=share/locale .build
ninja -C .build
ninja -C .build install
rm -f install_folder/share/glib-2.0/schemas/gschemas.compiled
rm -rf .build
rm meson.build
```

The content of the `install_folder` folder is what you must copy in the destination computers at /usr. Afterdoing that, you must run in each computer `sudo glib-compile-schemas /usr/share/glib-2.0/schemas` to update the schemas in the system.

## Export extension ZIP file for extensions.gnome.org

To create a ZIP file with the extension, just run:

```bash
./scripts/export-zip.sh
```

This will create the file `gtk4-ding@smedius.gitlab.com.zip` with the extension, following the rules for publishing at extensions.gnome.org.

## Contributing

Fixes are welcome, specially to this newer less tested Gtk4 version. Please file fixes and new ideas with an MR at Gitlab.

There are eslint rules in the repository, if able, please run eslint on all contributions so that they follow GJS/Gnome guidelines. The eslint.json is in the repository. The eslint-gjs.yml and eslint-shell.yml files are in the lint folder of the repository.

Translations are always required, the project uses gettext and there are po files in the repository.

## Source code and contacting the author

For the Gtk4 Desktop Icons NG (This repository)-

Sundeep Mediratta  
<https://gitlab.com/smedius/desktop-icons-ng>  
smedius@gmail.com

Sergio Costas is the author for the Original Desktop Icons NG. His project and contact information is here, however any errors in the Gtk4-Desktop
Icons are all mine, please do not spam him with problems from my fork.

Sergio Costas  
<https://gitlab.com/rastersoft/desktop-icons-ng>  
rastersoft@gmail.com
