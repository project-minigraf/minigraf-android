package io.github.project_minigraf.minigraf

// The override list (minigraf#872), as Minigraf.OVERRIDABLE_DEFAULTS in minigraf-java.

/**
 * The override list that applies when [OpenOptions.allowOverrides] is `null`: the
 * Rust `Overridable::DEFAULTS`, read from the core library. Pass a list to
 * `OpenOptions(allowOverrides = ...)` to replace it; an empty list refuses every
 * override keyword (API-025).
 */
val OVERRIDABLE_DEFAULTS: List<Overridable> by lazy { overridableDefaults() }
