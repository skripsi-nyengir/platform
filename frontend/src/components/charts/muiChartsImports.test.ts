import { describe, expect, it } from 'vitest';

describe('MUI X Charts Community import surface', () => {
  it('provides every renderer needed by this frontend', async () => {
    const [bar, line, scatter, sparkline] = await Promise.all([
      import('@mui/x-charts/BarChart'),
      import('@mui/x-charts/LineChart'),
      import('@mui/x-charts/ScatterChart'),
      import('@mui/x-charts/SparkLineChart'),
    ]);

    expect(bar.BarChart).toBeDefined();
    expect(line.LineChart).toBeDefined();
    expect(scatter.ScatterChart).toBeDefined();
    expect(sparkline.SparkLineChart).toBeDefined();
  });
});
