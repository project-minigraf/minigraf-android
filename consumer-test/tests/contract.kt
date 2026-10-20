// The consumer contract every binding checks (spec §4): in memory, file-backed
// across a reopen, and the error type for invalid Datalog.
package io.github.project_minigraf.consumer

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import org.junit.runner.RunWith
import io.github.project_minigraf.minigraf.MiniGrafDb
import io.github.project_minigraf.minigraf.MiniGrafException

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
    fun invalidDatalogThrowsMiniGrafException() {
        val db = MiniGrafDb.openInMemory()
        assertThrows(MiniGrafException::class.java) { db.execute("(query [:find") }
        db.close()
    }
}
