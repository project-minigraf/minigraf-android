package io.github.project_minigraf.minigraf

// Write transactions (minigraf#824), as MiniGrafDb.beginWrite(options) in minigraf-java.

/**
 * Begins a write transaction with [options]; see [MiniGrafDb.beginWrite]. An option
 * left `null` is the database's. Use it with `use { }`, which rolls back on exit
 * unless it was committed:
 *
 * ```kotlin
 * db.beginWrite(TxOptions(chunkFacts = 10_000)).use { tx ->
 *     tx.execute("(transact [[:alice :balance 90]])")
 *     tx.commit()
 * }
 * ```
 */
@Throws(MiniGrafException::class)
fun MiniGrafDb.beginWrite(options: TxOptions): MiniGrafWriteTransaction = beginWriteWith(options)
