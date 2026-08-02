Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\LEC\Desktop\Imvoi"
WshShell.Run """C:\Users\LEC\Desktop\Imvoi\.venv\Scripts\pythonw.exe"" ""C:\Users\LEC\Desktop\Imvoi\server.py""", 0, False
