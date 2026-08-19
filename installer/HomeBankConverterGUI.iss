#define VERSION "0.1.0"
#define BUNDLE_DIR "C:\Dev\Homebank-New\dist\HomeBankConverterGUI"
#define OUTPUT_DIR "C:\Dev\Homebank-New\releases"
#define ICON_FILE "C:\Users\username\OneDrive\Programming\Python\Homebank New\12218940.ico"

[Setup]
AppName=HomeBank Converter
AppVersion={#VERSION}
AppPublisher=HomeBank Converter
AppPublisherURL=https://github.com/
AppSupportURL=https://github.com/
AppUpdatesURL=https://github.com/
DefaultDirName={autopf}\HomeBank Converter
DefaultGroupName=HomeBank Converter
OutputBaseFilename=HomeBankConverterGUI-v{#VERSION}-setup
OutputDir={#OUTPUT_DIR}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
CreateAppDir=yes
CloseApplications=yes
SetupIconFile={#ICON_FILE}
UninstallDisplayIcon={app}\HomeBankConverterGUI.exe

[Files]
Source: "{#BUNDLE_DIR}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HomeBank Converter"; Filename: "{app}\HomeBankConverterGUI.exe"
Name: "{commondesktop}\HomeBank Converter"; Filename: "{app}\HomeBankConverterGUI.exe"

[Run]
Filename: "{app}\HomeBankConverterGUI.exe"; Description: "Launch HomeBank Converter"; Flags: nowait postinstall skipifsilent

[Code]
var
  SourceDirPage: TInputDirWizardPage;
  OutputDirPage: TInputDirWizardPage;

function NormalizeForJson(Value: string): string;
begin
  Result := Value;
  StringChangeEx(Result, '\', '/', True);
end;

function DetectPaymentRulesPath(): string;
var
  Candidates: array[0..3] of string;
  Index: Integer;
begin
  Candidates[0] := ExpandConstant('{app}\_internal\scripts\payment_rules.json');
  Candidates[1] := ExpandConstant('{app}\_internal\payment_rules.json');
  Candidates[2] := ExpandConstant('{app}\scripts\payment_rules.json');
  Candidates[3] := ExpandConstant('{app}\payment_rules.json');

  Result := Candidates[0];
  for Index := 0 to GetArrayLength(Candidates) - 1 do
  begin
    if FileExists(Candidates[Index]) then
    begin
      Result := Candidates[Index];
      Exit;
    end;
  end;
end;

procedure EnsureDirectoryExists(const DirectoryPath: string);
begin
  if not DirExists(DirectoryPath) then
  begin
    ForceDirectories(DirectoryPath);
  end;
end;

procedure SaveRuntimeConfig();
var
  ConfigPath: string;
  SourceDir: string;
  OutputBaseDir: string;
  HomeBankDir: string;
  PaymentRulesPath: string;
  ConfigBody: string;
begin
  SourceDir := RemoveBackslashUnlessRoot(SourceDirPage.Values[0]);
  OutputBaseDir := RemoveBackslashUnlessRoot(OutputDirPage.Values[0]);
  HomeBankDir := ExpandConstant('{userdocs}\HomeBank');
  PaymentRulesPath := DetectPaymentRulesPath();
  ConfigPath := ExpandConstant('{userprofile}\.homebank_converter.json');

  EnsureDirectoryExists(SourceDir);
  EnsureDirectoryExists(OutputBaseDir);
  EnsureDirectoryExists(HomeBankDir);
  EnsureDirectoryExists(AddBackslash(OutputBaseDir) + 'Import_Amex');
  EnsureDirectoryExists(AddBackslash(OutputBaseDir) + 'Import_Keytrade');
  EnsureDirectoryExists(AddBackslash(OutputBaseDir) + 'Import_Argenta');
  EnsureDirectoryExists(AddBackslash(OutputBaseDir) + 'Import_Mastercard');

  ConfigBody :=
    '{'#13#10 +
    '  "paths": {'#13#10 +
    '    "DOSSIER_SOURCE": "' + NormalizeForJson(SourceDir) + '",'#13#10 +
    '    "DOSSIER_SCRIPT": "' + NormalizeForJson(ExpandConstant('{app}')) + '",'#13#10 +
    '    "DOSSIER_HOMEBANK": "' + NormalizeForJson(HomeBankDir) + '",'#13#10 +
    '    "PAYMENT_RULES": "' + NormalizeForJson(PaymentRulesPath) + '",'#13#10 +
    '    "OUTPUT_LANGUAGE": "english",'#13#10 +
    '    "DOSSIER_SORTIE_AMEX": "' + NormalizeForJson(AddBackslash(OutputBaseDir) + 'Import_Amex') + '",'#13#10 +
    '    "DOSSIER_SORTIE_KEYTRADE": "' + NormalizeForJson(AddBackslash(OutputBaseDir) + 'Import_Keytrade') + '",'#13#10 +
    '    "DOSSIER_SORTIE_ARGENTA": "' + NormalizeForJson(AddBackslash(OutputBaseDir) + 'Import_Argenta') + '",'#13#10 +
    '    "DOSSIER_SORTIE_MASTERCARD": "' + NormalizeForJson(AddBackslash(OutputBaseDir) + 'Import_Mastercard') + '"'#13#10 +
    '  }'#13#10 +
    '}'#13#10;

  if not SaveStringToFile(ConfigPath, ConfigBody, False) then
  begin
    MsgBox(
      'Unable to save the HomeBank Converter configuration file to:' + #13#10 + ConfigPath,
      mbError,
      MB_OK
    );
  end;
end;

procedure InitializeWizard();
begin
  SourceDirPage := CreateInputDirPage(
    wpSelectDir,
    'Bank import file directory',
    'Choose the folder containing downloaded bank files',
    'Select the folder where your downloaded bank statements are stored.',
    False,
    ''
  );
  SourceDirPage.Add('');
  SourceDirPage.Values[0] := ExpandConstant('{userprofile}\Downloads');

  OutputDirPage := CreateInputDirPage(
    SourceDirPage.ID,
    'HomeBank output directory',
    'Choose the base folder for generated HomeBank import files',
    'The installer will create Import_Amex, Import_Keytrade, Import_Argenta, and Import_Mastercard subfolders in the selected location.',
    False,
    ''
  );
  OutputDirPage.Add('');
  OutputDirPage.Values[0] := ExpandConstant('{userprofile}\Downloads');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if (CurPageID = SourceDirPage.ID) and (Trim(SourceDirPage.Values[0]) = '') then
  begin
    MsgBox('Please select the folder containing your downloaded bank files.', mbError, MB_OK);
    Result := False;
  end
  else if (CurPageID = OutputDirPage.ID) and (Trim(OutputDirPage.Values[0]) = '') then
  begin
    MsgBox('Please select the base folder for the generated Import_* output folders.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveRuntimeConfig();
  end;
end;