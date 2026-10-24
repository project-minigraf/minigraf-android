package io.github.project_minigraf.minigraf

import java.util.UUID

// Plain Kotlin values for prepared queries (minigraf#181), as in minigraf-java.

/**
 * [v] as a bind value. `Boolean`; `Byte`, `Short`, `Int` and `Long` as integers;
 * `Float` and `Double` as floats; `String`; `null`; and `java.util.UUID` (an
 * entity, which also fits value and rule-argument slots) bind as they are, as do
 * a [MiniGrafValue] and a [MiniGrafBindValue]. Any other type is
 * [IllegalArgumentException].
 */
fun bindValue(name: String, v: Any?): MiniGrafBindValue = when (v) {
    null -> MiniGrafBindValue.Value(MiniGrafValue.Null)
    is MiniGrafBindValue -> v
    is MiniGrafValue -> MiniGrafBindValue.Value(v)
    is Boolean -> MiniGrafBindValue.Value(MiniGrafValue.Bool(v))
    is Byte, is Short, is Int, is Long -> MiniGrafBindValue.Value(MiniGrafValue.Int64((v as Number).toLong()))
    is Float, is Double -> MiniGrafBindValue.Value(MiniGrafValue.Float64((v as Number).toDouble()))
    is String -> MiniGrafBindValue.Value(MiniGrafValue.Text(v))
    is UUID -> MiniGrafBindValue.Entity(v.toString())
    else -> throw IllegalArgumentException(
        "slot \$$name: cannot bind a ${v::class.java.name}; use Boolean, an integer or " +
            "floating type, String, null, UUID, a MiniGrafValue or a MiniGrafBindValue",
    )
}

private fun bindValues(bindings: Map<String, Any?>): Map<String, MiniGrafBindValue> =
    bindings.mapValues { (name, v) -> bindValue(name, v) }

/** Runs the query with [bindings] (`"slot" to value`, no `$`) and returns its JSON. */
fun MiniGrafPreparedQuery.execute(vararg bindings: Pair<String, Any?>): String =
    execute(bindValues(bindings.toMap()))

/** Runs the query with [bindings] and returns a cursor over its rows. */
fun MiniGrafPreparedQuery.query(vararg bindings: Pair<String, Any?>): MiniGrafCursor =
    query(bindValues(bindings.toMap()))
