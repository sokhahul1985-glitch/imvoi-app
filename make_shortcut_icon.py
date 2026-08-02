import os
from PIL import Image

def update_all_shortcuts():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "cmp_logo.png")
    ico_path = os.path.join(base_dir, "app_icon.ico")
    vbs_launcher = os.path.join(base_dir, "run_hidden.vbs")
    
    if not os.path.exists(logo_path):
        import generate_logo
        generate_logo.create_cmp_logo()
        
    img = Image.open(logo_path)
    img.save(ico_path, format="ICO", sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print(f"ICO file ready at: {ico_path}")
    
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_names = ["run_php_app.lnk", "run_php_app - Shortcut.lnk"]
    
    vbs_lines = [
        'Set WshShell = CreateObject("WScript.Shell")',
        'Set fso = CreateObject("Scripting.FileSystemObject")'
    ]
    
    for name in shortcut_names:
        shortcut_path = os.path.join(desktop, name).replace("\\", "\\\\")
        vbs_lines.append(f'path = "{shortcut_path}"')
        vbs_lines.append('If fso.FileExists(path) Then')
        vbs_lines.append('  Set shortcut = WshShell.CreateShortcut(path)')
        vbs_lines.append(f'  shortcut.TargetPath = "wscript.exe"')
        vbs_lines.append(f'  shortcut.Arguments = """{vbs_launcher.replace("\\", "\\\\")}"""')
        vbs_lines.append(f'  shortcut.WorkingDirectory = "{base_dir.replace("\\", "\\\\")}"')
        vbs_lines.append(f'  shortcut.IconLocation = "{ico_path.replace("\\", "\\\\")}"')
        vbs_lines.append('  shortcut.Save()')
        vbs_lines.append('End If')
        
    vbs_path = os.path.join(base_dir, "update_shortcuts.vbs")
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write("\n".join(vbs_lines))
        
    os.system(f'cscript //nologo "{vbs_path}"')
    print("Desktop shortcuts updated to run silently without command prompt window!")

if __name__ == "__main__":
    update_all_shortcuts()
