Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
path = "C:\\Users\\LEC\\Desktop\\run_php_app.lnk"
If fso.FileExists(path) Then
  Set shortcut = WshShell.CreateShortcut(path)
  shortcut.TargetPath = "wscript.exe"
  shortcut.Arguments = """C:\\Users\\LEC\\Desktop\\Imvoi\\run_hidden.vbs"""
  shortcut.WorkingDirectory = "C:\\Users\\LEC\\Desktop\\Imvoi"
  shortcut.IconLocation = "C:\\Users\\LEC\\Desktop\\Imvoi\\app_icon.ico"
  shortcut.Save()
End If
path = "C:\\Users\\LEC\\Desktop\\run_php_app - Shortcut.lnk"
If fso.FileExists(path) Then
  Set shortcut = WshShell.CreateShortcut(path)
  shortcut.TargetPath = "wscript.exe"
  shortcut.Arguments = """C:\\Users\\LEC\\Desktop\\Imvoi\\run_hidden.vbs"""
  shortcut.WorkingDirectory = "C:\\Users\\LEC\\Desktop\\Imvoi"
  shortcut.IconLocation = "C:\\Users\\LEC\\Desktop\\Imvoi\\app_icon.ico"
  shortcut.Save()
End If