' Silent background launcher (no black console window)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim py
py = ".venv\Scripts\pythonw.exe"
If Not CreateObject("Scripting.FileSystemObject").FileExists(sh.CurrentDirectory & "\" & py) Then
  py = "pythonw"
End If

sh.Run """" & py & """ -m jarvis --background", 0, False
