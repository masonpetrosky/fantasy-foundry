export function normalizeCalculatorRunSettingsInput<T>(
  runSettings: unknown,
  currentSettings: T,
): T {
  if (runSettings == null) return currentSettings;
  if (
    runSettings &&
    typeof runSettings === "object" &&
    Object.prototype.hasOwnProperty.call(runSettings, "nativeEvent")
  ) {
    return currentSettings;
  }
  return runSettings as T;
}
