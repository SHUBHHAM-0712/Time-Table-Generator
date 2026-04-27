-- Migration: Add merge tracking columns to master_timetable
-- Purpose: Track which batches are merged for a single lecture slot

ALTER TABLE master_timetable 
ADD COLUMN merged_batch_ids TEXT,
ADD COLUMN is_merged BOOLEAN DEFAULT FALSE;

-- merged_batch_ids format: '1,2,3,4' (comma-separated batch IDs in the merge)
-- is_merged: TRUE if this lecture is shared by multiple batches (merge scenario)
--           FALSE if this is a single batch lecture

CREATE INDEX idx_master_timetable_is_merged ON master_timetable (run_id, is_merged);
