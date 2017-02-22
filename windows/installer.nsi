;--------------------------------
;Include Modern UI

!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_KEY "Software\Plover\${version}"
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_VALUENAME ""
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_KEY "Software\Plover\${version}"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_VALUENAME ""
!define MULTIUSER_INSTALLMODE_INSTDIR "Plover ${version}"
!include MultiUser.nsh
!include MUI2.nsh

;--------------------------------
;General

  ;Name and file
  Name "Plover"

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING
  !define MUI_ICON "${srcdir}\plover.ico"

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_LICENSE "${srcdir}\LICENSE.txt"
  !insertmacro MULTIUSER_PAGE_INSTALLMODE
  !insertmacro MUI_PAGE_DIRECTORY

  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "SHCTX" 
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\Plover\${version}" 
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
  !insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder

  !insertmacro MUI_PAGE_INSTFILES
  
  !define MUI_FINISHPAGE_RUN $INSTDIR\plover.exe
  !define MUI_FINISHPAGE_RUN_PARAMETERS ""
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "Plover" BfWSection

  SetOutPath "$INSTDIR"

  File "${srcdir}\LICENSE.txt"
  File "${srcdir}\plover.exe"
  File "${srcdir}\plover.ico"
  File "${srcdir}\plover_console.exe"
  File "${srcdir}\plover_plugin_install.exe"
  File /r "${srcdir}\data"
  
  ;Store installation folder
  WriteRegStr SHCTX "Software\Plover\${version}" "" "$INSTDIR"
  
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    ;Create shortcuts
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Plover.lnk" "$INSTDIR\plover.exe" "" "$INSTDIR\plover.ico"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Plover (debug).lnk" "$INSTDIR\plover_console.exe" "-l debug" "$INSTDIR\plover.ico"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

;--------------------------------
;Installer Functions

  Function .onInit
    !insertmacro MULTIUSER_INIT
  FunctionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  RMDir /r "$INSTDIR\data"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\plover.exe"
  Delete "$INSTDIR\plover.ico"
  Delete "$INSTDIR\plover_console.exe"
  Delete "$INSTDIR\plover_plugin_install.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"

  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
  Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
  Delete "$SMPROGRAMS\$StartMenuFolder\Plover.lnk"
  Delete "$SMPROGRAMS\$StartMenuFolder\Plover (debug).lnk"
  RMDir "$SMPROGRAMS\$StartMenuFolder"
 
  DeleteRegKey /ifempty SHCTX "Software\Plover\${version}"
  DeleteRegKey /ifempty SHCTX "Software\Plover"

SectionEnd

;--------------------------------
;Uninstaller Functions

  Function un.onInit
    !insertmacro MULTIUSER_UNINIT
  FunctionEnd
