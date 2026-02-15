export function normalizeCalculatorRunSettingsInput(runSettings, currentSettings) {
  if (runSettings == null) return currentSettings;
  if (
    runSettings &&
    typeof runSettings === "object" &&
    Object.prototype.hasOwnProperty.call(runSettings, "nativeEvent")
  ) {
    return currentSettings;
  }
  return runSettings;
}
