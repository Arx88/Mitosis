import { useState, useEffect, useRef } from 'react';

/**
 * Formats elapsed seconds into a MM:SS string.
 * @param totalSeconds The total seconds elapsed.
 * @returns A string in MM:SS format.
 */
const formatTime = (totalSeconds: number): string => {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes)}:${String(seconds).padStart(2, '0')}`;
};

/**
 * Custom hook to manage a timer that runs when `isActive` is true.
 * It returns a formatted time string (MM:SS) of the elapsed time.
 * The timer resets when `isActive` transitions from false to true.
 *
 * @param isActive Controls whether the timer should be running.
 * @returns Formatted time string (e.g., "0:42").
 */
export const useThinkingTimer = (isActive: boolean): string => {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const prevIsActiveRef = useRef<boolean>(false);

  useEffect(() => {
    // Handle starting or resetting the timer
    if (isActive && !prevIsActiveRef.current) {
      setElapsedSeconds(0); // Reset timer when it becomes active
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      intervalRef.current = setInterval(() => {
        setElapsedSeconds((prevSeconds) => prevSeconds + 1);
      }, 1000);
    } else if (!isActive && prevIsActiveRef.current) {
      // Handle stopping the timer
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      // Optionally, you might want to keep elapsedSeconds as is, or reset it here too
      // For now, it keeps the last value when stopped.
    }

    // Store current isActive state for next render
    prevIsActiveRef.current = isActive;

    // Cleanup on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isActive]);

  return formatTime(elapsedSeconds);
};
