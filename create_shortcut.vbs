
Set WshShell = CreateObject("WScript.Shell")
Set shortcut = WshShell.CreateShortcut("C:\Users\LEC\Desktop\run_php_app.lnk")
shortcut.TargetPath = "C:\Users\LEC\Desktop\Imvoi\run_php_app.bat"
shortcut.WorkingDirectory = "C:\Users\LEC\Desktop\Imvoi"
shortcut.IconLocation = "C:\Users\LEC\Desktop\Imvoi\app_icon.ico"
shortcut.Description = "CMP Imvoi Application"
shortcut.Save()
