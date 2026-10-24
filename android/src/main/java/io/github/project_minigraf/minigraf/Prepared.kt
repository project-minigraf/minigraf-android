package io.github.project_minigraf.minigraf

import java.util.UUID

// Plain Kotlin values for prepared queries (minigraf#181), as in minigraf-java.

/**
 * [v] as a bind value. `Boolean`; `Byte`, `Short`, `Int` and `Long` as integers;
 * `Float` and `Double` as floats; `String`; `null`; and `java.util.UUID` (an
 * entity, which also fits value and rule-argument slots) bind as they are, as do
 * a [MiniGrafValue] and a [MiniGrafBindValue]. A `Set` binds a set value
 * (minigraf#316): its elements are any of those plain values or a [MiniGrafValue],
 * and a `UUID` element is a ref. Any other type, or a set element that is not a
 * value, is [IllegalArgumentException].
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
    is kotlin.collections.Set<*> -> MiniGrafBindValue.Value(MiniGrafValue.Set(v.map { setElement(name, it) }))
    else -> throw IllegalArgumentException(
        "slot \$$name: cannot bind a ${v::class.java.name}; use Boolean, an integer or " +
            "floating type, String, null, UUID, Set, a MiniGrafValue or a MiniGrafBindValue",
    )
}

/** An element of a `Set` bind value. A set element is passed on, for core's API-021. */
private fun setElement(name: String, e: Any?): MiniGrafValue = when (e) {
    is UUID -> MiniGrafValue.Ref(e.toString())
    else -> when (val b = bindValue(name, e)) {
        is MiniGrafBindValue.Value -> b.value
        else -> throw IllegalArgumentException("slot \$$name: a set element must be a value")
    }
}

private fun bindValues(bindings: Map<String, Any?>): Map<String, MiniGrafBindValue> =
    bindings.mapValues { (name, v) -> bindValue(name, v) }

/** Runs the query with [bindings] (`"slot" to value`, no `$`) and returns its JSON. */
fun MiniGrafPreparedQuery.execute(vararg bindings: Pair<String, Any?>): String =
    execute(bindValues(bindings.toMap()))

/** Runs the query with [bindings] and returns a cursor over its rows. */
fun MiniGrafPreparedQuery.query(vararg bindings: Pair<String, Any?>): MiniGrafCursor =
    query(bindValues(bindings.toMap()))
