// The consumer contract every binding checks (spec §4): in memory, file-backed
// across a reopen, prepared queries, set values, user functions, and the error
// type for invalid Datalog.
package io.github.project_minigraf.consumer

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import io.github.project_minigraf.minigraf.MiniGrafAccumulator
import io.github.project_minigraf.minigraf.MiniGrafAggregate
import io.github.project_minigraf.minigraf.MiniGrafDb
import io.github.project_minigraf.minigraf.MiniGrafException
import io.github.project_minigraf.minigraf.MiniGrafPredicate
import io.github.project_minigraf.minigraf.MiniGrafValue
import io.github.project_minigraf.minigraf.execute

@RunWith(AndroidJUnit4::class)
class Contract {
    private val query = "(query [:find ?n :where [?e :name ?n]])"

    private fun names(json: String): List<String> {
        val rows = JSONObject(json).getJSONArray("results")
        return (0 until rows.length()).map { rows.getJSONArray(it).getString(0) }
    }

    @Test
    fun inMemory() {
        val db = MiniGrafDb.openInMemory()
        db.execute("""(transact [[:alice :name "Alice"]])""")
        assertEquals(listOf("Alice"), names(db.execute(query)))
        db.close()
    }

    @Test
    fun fileBackedSurvivesReopen() {
        val cache = InstrumentationRegistry.getInstrumentation().targetContext.cacheDir
        val dir = File(cache, "contract-${System.nanoTime()}").apply { mkdirs() }
        val path = File(dir, "test.graph").path

        val db = MiniGrafDb.open(path)
        db.execute("""(transact [[:bob :name "Bob"]])""")
        db.checkpoint()
        db.close()

        val reopened = MiniGrafDb.open(path)
        assertEquals(listOf("Bob"), names(reopened.execute(query)))
        reopened.close()
        dir.deleteRecursively()
    }

    @Test
    fun preparedQueryRunsWithPlainAndTypedValues() {
        val db = MiniGrafDb.openInMemory()
        db.execute("""(transact [[:alice :name "Alice"] [:bob :name "Bob"]])""")
        val pq = db.prepare("(query [:find ?n :where [?e :name \$name] [?e :name ?n]])")
        for (name in listOf("Alice", "Bob")) {
            assertEquals(listOf(name), names(pq.execute("name" to name)))
        }
        assertEquals(listOf("Alice"), names(pq.execute("name" to MiniGrafValue.Text("Alice"))))
        val e = assertThrows(MiniGrafException.Api::class.java) { pq.execute() }
        assertEquals("[API-022]", e.msg.take(9))
        pq.close()
        db.close()
    }

    @Test
    fun setValuesComeBackAndBind() {
        val db = MiniGrafDb.openInMemory()
        db.execute("""(transact [[:alice :tags #{1 :k "x"}] [:alice :name "Alice"]])""")
        val tags = JSONObject(db.execute("(query [:find ?t :where [?e :tags ?t]])"))
            .getJSONArray("results").getJSONArray(0).getJSONArray(0)
        assertEquals("""["x",1,":k"]""", tags.toString())
        val member = db.prepare("(query [:find ?n :where [?e :tags ?t] [(in? 1 \$s)] [?e :name ?n]])")
        assertEquals(listOf("Alice"), names(member.execute("s" to setOf(1, 2))))
        val equal = db.prepare("(query [:find ?n :where [?e :tags \$s] [?e :name ?n]])")
        assertEquals(listOf("Alice"), names(equal.execute("s" to setOf(1, "x", MiniGrafValue.Keyword(":k")))))
        val e = assertThrows(MiniGrafException.Api::class.java) { member.execute("s" to setOf(setOf(1))) }
        assertEquals("[API-021]", e.msg.take(9))
        member.close()
        equal.close()
        db.close()
    }

    @Test
    fun userPredicateAndAggregate() {
        val db = MiniGrafDb.openInMemory()
        db.execute("""(transact [[:alice :name "Alice"] [:alice :age 30] [:bob :name "Bob"] [:bob :age 12]])""")
        db.registerPredicate("adult?", object : MiniGrafPredicate {
            override fun test(value: MiniGrafValue): Boolean = (value as MiniGrafValue.Int64).value >= 18
        })
        db.registerAggregate("product", object : MiniGrafAggregate {
            override fun accumulator(): MiniGrafAccumulator = object : MiniGrafAccumulator {
                private var product = 1L
                override fun step(value: MiniGrafValue) {
                    val n = (value as MiniGrafValue.Int64).value
                    if (n == 0L) throw IllegalArgumentException("zero")
                    product *= n
                }
                override fun finish(count: Long): MiniGrafValue = MiniGrafValue.Int64(product)
            }
        })
        assertEquals(listOf("Alice"), names(db.execute("(query [:find ?n :where [?e :age ?a] [(adult? ?a)] [?e :name ?n]])")))
        val product = JSONObject(db.execute("(query [:find (product ?a) :where [?e :age ?a]])"))
            .getJSONArray("results").getJSONArray(0).getLong(0)
        assertEquals(360L, product)
        db.execute("(transact [[:carol :age 0]])")
        val e = assertThrows(MiniGrafException.Query::class.java) {
            db.execute("(query [:find (product ?a) :where [?e :age ?a]])")
        }
        assertEquals("[QRY-014]", e.msg.take(9))
        assertTrue(e.msg.contains("zero"))
        db.close()
    }

    @Test
    fun invalidDatalogThrowsMiniGrafException() {
        val db = MiniGrafDb.openInMemory()
        assertThrows(MiniGrafException::class.java) { db.execute("(query [:find") }
        db.close()
    }
}
