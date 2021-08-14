from tindeq import TindeqProgressor
from scipy import constants as cnst
import matplotlib.animation as animation
from matplotlib.widgets import Button
import matplotlib.pyplot as plt
from collections import deque
import asyncio
import threading

class PeakForce():
  units={'lb' : 1.0 / cnst.lb, 'kg' : 1.0 }
  def __init__(self, unit='kg'):
    if unit not in PeakForce.units:
      raise RuntimeError('unit=[\'kg\'|\'lb\']')
    self.unit_scale = PeakForce.units[unit]
    self.unit_name = unit

    self.fig,self.ax = plt.subplots()
    self.fig.tight_layout()
    self.fig.canvas.mpl_connect('close_event', self.close)
    self.fig.canvas.set_window_title('Peak Force')

    plt.subplots_adjust(bottom=0.2)
    self.aStart = plt.axes([0.7, 0.05, 0.1, 0.075])
    self.bStart = Button(self.aStart, 'Start')
    self.bStart.on_clicked(self.sstart)
    self.aStop = plt.axes([0.81, 0.05, 0.1, 0.075])
    self.bStop = Button(self.aStop, 'Stop')
    self.bStop.on_clicked(self.sstop)
    
    self.cStartThresh=4.0
    self.cStopThresh=2.0
    self.dq = deque()
    self.plotx = []
    self.ploty = []
    self.plots = []
    self.t0=[]
    self.tindeq = None
    self.statmsg = "Init..."
    self.running = True
    self.collecting = False
    self.above_thresh = False

  def close(self, e):
    self.collecting = False
    self.running = False

  def update_plot(self,n):
    # FIXME: This is very inefficient, should do it with blit=True but the documentation
    # for that seems devoid of most helpful detail. I guess I have to learn a whole lot about
    # matplotlib.Artist et al first.
    self.ax.clear()
    while len(self.dq) > 1:
      pt = self.dq.popleft()
      if pt[1] > self.cStartThresh:
        if not self.above_thresh:
          self.plotx.append([])
          self.ploty.append([])
          self.t0.append(pt[0])
        self.above_thresh = True
      if pt[1] < self.cStopThresh:
        self.above_thresh = False

      if self.above_thresh:
        self.plotx[-1].append(pt[0] - self.t0[-1])
        self.ploty[-1].append(self.unit_scale * pt[1])
    self.ax.set_title(self.statmsg)
    for i in range(len(self.plotx)):
      if len(self.ploty) > 0:
        mm = max(self.ploty[i])
        self.ax.plot(self.plotx[i],self.ploty[i], label="{:.2f} kg".format(mm))
        self.ax.legend()

  def sstart(self, e):
    self.plotx = []
    self.ploty = []
    self.t0=[]
    self.collecting = True

  def sstop(self, e):
    self.collecting = False

  def log_force_sample(self, time, weight):
    '''Callback with data update from the progressor'''
    self.dq.append([time,weight])

  def start(self):
    self.animator=animation.FuncAnimation(self.fig, self.update_plot, interval=500, blit=False)
    plt.show()

pf = PeakForce('kg')
t = TindeqProgressor(pf)
pf.tindeq = t

# FIXME: Either python async stuff is clunky and awful or I'm just a bit dumb (proably both)
# either way this thread/loop/wrap/loop nonsense seems like the not-right way to do this
async def tindeq_loop():
  try:
    await t.connect()
    pf.statmsg="Connected"
    was_collecting = False
    while pf.running:
      if pf.collecting and not was_collecting:
        await t.start_logging_weight()
        await asyncio.sleep(1)
        pf.statmsg="Pull to Start"
      if not pf.collecting and was_collecting:
        await t.stop_logging_weight()
        pf.statmsg="Connected"
      was_collecting = pf.collecting
      await asyncio.sleep(1)
  except:
    pf.statmsg="Connection Failed"
    await asyncio.sleep(1)
    pf.statmsg="Reconnecting"
    print("Failed to find Tindeq")

def tindeq_loop_wrapper():
  pf.loop = asyncio.new_event_loop()
  pf.statmsg = "Connecting"
  while pf.running:
    pf.loop.run_until_complete(tindeq_loop())
  try:
    pf.loop.run_until_complete(t.disconnect())
  except:
    print("Failed to disconnect, maybe it was not connected?")

if __name__ == "__main__":
  trd = threading.Thread(target=tindeq_loop_wrapper)
  trd.start()
  pf.start()
