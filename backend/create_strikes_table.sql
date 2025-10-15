-- Create strikes table to track missed deadlines and violations
CREATE TABLE strikes (
  id SERIAL PRIMARY KEY,
  habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  reason TEXT NOT NULL,
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add indexes for faster queries
CREATE INDEX idx_strikes_habit_id ON strikes(habit_id);
CREATE INDEX idx_strikes_date ON strikes(date);
