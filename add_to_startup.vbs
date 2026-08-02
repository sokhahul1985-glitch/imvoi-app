Set WshShell = CreateObject("WScript.Shell")
startupFolder = WshShell.SpecialFolders("Startup")
shortcutPath = startupFolder & "\Imvoi_Web_Server.lnk"

Set shortcut = WshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """C:\Users\LEC\Desktop\Imvoi\run_hidden.vbs"""
shortcut.WorkingDirectory = "C:\Users\LEC\Desktop\Imvoi"
shortcut.IconLocation = "C:\Users\LEC\Desktop\Imvoi\app_icon.ico"
shortcut.Save

WScript.Echo "Startup Shortcut Created Successfully at: " & shortcutPath
