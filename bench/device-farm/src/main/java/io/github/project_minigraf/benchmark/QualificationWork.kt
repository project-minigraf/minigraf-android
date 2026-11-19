package io.github.project_minigraf.benchmark

/** Only the qualification slowdown path calls this. Setup and checks are untimed. */
object QualificationWork {
    fun <S, T> invoke(setup: () -> S, action: (S) -> T, validate: (T) -> Unit,
                      cleanup: (S) -> Unit, clock: () -> Long): Long {
        val first = setup()
        val second = try { setup() } catch (failure: Throwable) {
            try { cleanup(first) } catch (error: Throwable) { failure.addSuppressed(error) }
            throw failure
        }
        var failure: Throwable? = null
        fun attempt(block: () -> Unit) {
            try { block() } catch (error: Throwable) {
                if (failure == null) failure = error else failure!!.addSuppressed(error)
            }
        }
        var elapsed = 0L
        attempt {
            val start = clock()
            val firstValue = action(first)
            val secondValue = action(second)
            elapsed = clock() - start
            attempt { validate(firstValue) }
            attempt { validate(secondValue) }
        }
        attempt { cleanup(first) }
        attempt { cleanup(second) }
        failure?.let { throw it }
        return elapsed
    }
}
