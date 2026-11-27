package io.github.project_minigraf.benchmark

import org.junit.Assert.assertThrows
import org.junit.Test
import org.junit.Assert.*

class ResultChecksTest {
    private val expected = listOf(0L, 1L, 2L, 3L)

    @Test fun acceptsCompleteUnorderedResult() {
        ResultChecks.numbers(listOf(3L, 1L, 0L, 2L), expected)
    }

    @Test fun rejectsMissingRows() {
        assertThrows(IllegalArgumentException::class.java) {
            ResultChecks.numbers(emptyList(), expected)
        }
    }

    @Test fun rejectsWrongValuesDespiteEqualCountAndSum() {
        assertThrows(IllegalArgumentException::class.java) {
            ResultChecks.numbers(listOf(0L, 0L, 3L, 3L), expected)
        }
    }

    @Test fun platformRequiresCorroborationAndLoadedAbi() {
        fun identity(fingerprint: String, hardware: String, product: String, qemu: String,
                     bootQemu: String, abis: List<String>, loaded: String) =
            PlatformIdentity.classify(fingerprint, hardware, product, qemu, bootQemu,
                abis, "Pixel 7", 34, loaded)
        assertEquals("physical", identity("google/panther/panther:14/release-keys", "panther",
            "panther", "", "", listOf("arm64-v8a"), "arm64-v8a"))
        assertEquals("emulator", identity("google/sdk_gphone64_x86_64:14", "ranchu",
            "sdk_gphone64_x86_64", "1", "1", listOf("x86_64"), "x86_64"))
        assertEquals("unknown", identity("generic", "board", "product", "", "",
            listOf("arm64-v8a"), "arm64-v8a"))
        assertEquals("unknown", identity("google/panther:14", "panther", "panther", "", "",
            listOf("arm64-v8a"), "x86_64"))
        assertEquals("unknown", identity("google/panther:14", "panther", "panther", "1", "",
            listOf("arm64-v8a"), "arm64-v8a"))
    }

    @Test fun elfAbiUsesTheLoadedBytes() {
        fun elf(machine: Int) = ByteArray(64).also {
            it[0] = 0x7f; it[1] = 69; it[2] = 76; it[3] = 70
            it[4] = 2; it[5] = 1; it[18] = machine.toByte()
        }
        assertEquals("arm64-v8a", PlatformIdentity.elfAbi(elf(183)))
        assertEquals("x86_64", PlatformIdentity.elfAbi(elf(62)))
        assertThrows(IllegalArgumentException::class.java) { PlatformIdentity.elfAbi(elf(3)) }
        assertThrows(IllegalArgumentException::class.java) { PlatformIdentity.elfAbi(ByteArray(64)) }
    }

    @Test fun doubledWorkHasTwoUntimedIndependentFixturesAndValidations() {
        val events = mutableListOf<String>()
        var sequence = 0
        var tick = 0L
        val elapsed = QualificationWork.invoke(
            setup = { (++sequence).also { events += "setup$it" } },
            action = { events += "action$it"; listOf(it.toLong()) },
            validate = { events += "check${it.single()}" },
            cleanup = { events += "close$it" },
            clock = { events += "clock"; (++tick) * 100 })
        assertEquals(100L, elapsed)
        assertEquals(listOf("setup1", "setup2", "clock", "action1", "action2", "clock",
            "check1", "check2", "close1", "close2"), events)
    }

    @Test fun wrongFirstResultStillChecksAndClosesSecondFixture() {
        var sequence = 0
        val checked = mutableListOf<Int>()
        val closed = mutableListOf<Int>()
        assertThrows(IllegalArgumentException::class.java) {
            QualificationWork.invoke(setup = { ++sequence }, action = { it },
                validate = { checked += it; require(it != 1) },
                cleanup = { closed += it }, clock = { 0L })
        }
        assertEquals(listOf(1, 2), checked)
        assertEquals(listOf(1, 2), closed)
    }

    @Test fun secondSetupFailureClosesFirstAndCleanupFailureClosesBoth() {
        var sequence = 0
        val closed = mutableListOf<Int>()
        assertThrows(IllegalStateException::class.java) {
            QualificationWork.invoke(setup = { check(++sequence != 2); sequence },
                action = { it }, validate = {}, cleanup = { closed += it }, clock = { 0L })
        }
        assertEquals(listOf(1), closed)
        sequence = 0; closed.clear()
        assertThrows(IllegalStateException::class.java) {
            QualificationWork.invoke(setup = { ++sequence }, action = { it }, validate = {},
                cleanup = { closed += it; check(it != 1) }, clock = { 0L })
        }
        assertEquals(listOf(1, 2), closed)
    }
}
