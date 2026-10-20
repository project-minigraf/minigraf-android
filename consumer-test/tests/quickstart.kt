// The README quick start, line for line (readme_sync.py checks this), wrapped
// in a test.
package io.github.project_minigraf.consumer

import io.github.project_minigraf.minigraf.MiniGrafDb

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class Quickstart {
    @Test
    fun readmeQuickStart() {
        val db = MiniGrafDb.openInMemory()
        val result = db.execute("""(transact [[:alice :name "Alice"]])""")
        println(result)  // {"transacted":<tx id>}
        assertTrue(result.startsWith("{\"transacted\":"))
    }
}
