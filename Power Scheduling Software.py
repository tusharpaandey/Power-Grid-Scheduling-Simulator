import tkinter as tk
from tkinter import ttk, messagebox
import math
import random

# --- Core Simulation Logic (adapted from previous script) ---

class PowerPlant:
    """
    Represents a single power generation plant with added GUI update capabilities.
    """
    def __init__(self, name, plant_type, capacity_mw, rate_usd_per_mwh, min_gen_mw):
        self.name = name
        self.plant_type = plant_type
        self.original_capacity_mw = capacity_mw
        self.capacity_mw = capacity_mw
        self.rate_usd_per_mwh = rate_usd_per_mwh
        self.min_gen_mw = min_gen_mw
        self.status = "OFF"
        self.current_dispatch_mw = 0

    def turn_on(self):
        if self.status != "FORCED_OUTAGE":
            self.status = "ON"
            self.current_dispatch_mw = self.min_gen_mw
        else:
            self.current_dispatch_mw = 0

    def turn_off(self):
        self.status = "OFF"
        self.current_dispatch_mw = 0

    def force_outage(self):
        self.status = "FORCED_OUTAGE"
        self.current_dispatch_mw = 0
        messagebox.showwarning("Forced Outage", f"ALERT: Forced outage reported for {self.name}!")

    def update_solar_capacity(self, time_block):
        if self.plant_type == "SOLAR":
            radian_equivalent = (time_block / 96.0) * 2 * math.pi
            solar_factor = max(0, math.sin(radian_equivalent - math.pi / 2) + 0.1)
            self.capacity_mw = self.original_capacity_mw * solar_factor

class Scheduler:
    """
    Manages scheduling logic and holds the state of the simulation.
    """
    def __init__(self, plants):
        self.plants = sorted(plants, key=lambda p: p.rate_usd_per_mwh)
        self.daily_summary = {
            "total_cost": 0,
            "total_energy_mwh": 0,
            "shortfall_events": 0,
            "total_shortfall_mwh": 0
        }

    def schedule_for_block(self, demand_mw, time_block):
        # Update solar capacity for the current time block
        for plant in self.plants:
            plant.update_solar_capacity(time_block)

        # Reset dispatch for all plants that are ON to their minimum generation
        for plant in self.plants:
            if plant.status == "ON":
                plant.current_dispatch_mw = plant.min_gen_mw
            else:
                plant.current_dispatch_mw = 0
        
        # Calculate initial dispatched power from plants already ON
        dispatched_power = sum(p.current_dispatch_mw for p in self.plants if p.status == "ON")

        # Unit Commitment: Turn on cheapest available plants if initial power is not enough
        if dispatched_power < demand_mw:
            for plant in self.plants: # Iterate in merit order (cheapest first)
                if plant.status == "OFF":
                    plant.turn_on()
                    dispatched_power += plant.current_dispatch_mw
                    if dispatched_power >= demand_mw:
                        break

        # Economic Dispatch: Ramp up ON plants to meet the remaining demand
        needed_power = demand_mw - dispatched_power
        if needed_power > 0:
            for plant in self.plants: # Iterate in merit order
                if plant.status == "ON":
                    available_ramp_capacity = plant.capacity_mw - plant.current_dispatch_mw
                    dispatch_increase = min(needed_power, available_ramp_capacity)
                    
                    plant.current_dispatch_mw += dispatch_increase
                    dispatched_power += dispatch_increase
                    needed_power -= dispatch_increase

                    if needed_power <= 0:
                        break
        
        shortfall = demand_mw - dispatched_power
        block_cost = sum(p.current_dispatch_mw * p.rate_usd_per_mwh * 0.25 for p in self.plants)
        
        self.daily_summary["total_cost"] += block_cost
        self.daily_summary["total_energy_mwh"] += dispatched_power * 0.25
        if shortfall > 0:
            self.daily_summary["shortfall_events"] += 1
            self.daily_summary["total_shortfall_mwh"] += shortfall * 0.25
            
        return dispatched_power, shortfall, block_cost

# --- GUI Application ---

class PowerDashboard(tk.Tk):
    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler
        self.current_block = 0
        self.title("Power Scheduling Dashboard")
        self.geometry("1400x800")

        # Apply a modern theme
        self.style = ttk.Style(self)
        self.style.theme_use("clam") # Options: clam, alt, default, classic

        # Configure styles
        self.style.configure("Treeview", rowheight=25, font=('Calibri', 10))
        self.style.configure("Treeview.Heading", font=('Calibri', 11, 'bold'))
        self.style.configure("TLabel", font=('Calibri', 12))
        self.style.configure("TButton", font=('Calibri', 11, 'bold'))
        self.style.configure("Header.TLabel", font=('Calibri', 18, 'bold'))

        self._create_widgets()
        self._populate_initial_data()

    def _create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_label = ttk.Label(main_frame, text="Real-Time Power Grid Dashboard", style="Header.TLabel")
        header_label.pack(pady=10)

        # Top frame for controls and summary
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        # --- Controls ---
        controls_frame = ttk.LabelFrame(top_frame, text="Simulation Controls", padding="10")
        controls_frame.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        self.run_button = ttk.Button(controls_frame, text="Run Next Block", command=self.run_next_block)
        self.run_button.pack(side=tk.LEFT, padx=5)

        self.backdown_button = ttk.Button(controls_frame, text="Backdown/Startup Plant", command=self.toggle_plant_status)
        self.backdown_button.pack(side=tk.LEFT, padx=5)
        
        self.outage_button = ttk.Button(controls_frame, text="Declare Forced Outage", command=self.declare_outage)
        self.outage_button.pack(side=tk.LEFT, padx=5)

        # --- Summary ---
        summary_frame = ttk.LabelFrame(top_frame, text="Daily Summary", padding="10")
        summary_frame.pack(side=tk.RIGHT, padx=10, fill=tk.X, expand=True)

        self.cost_label = ttk.Label(summary_frame, text="Total Cost: ₹0.00")
        self.cost_label.pack(anchor="w")
        self.shortfall_label = ttk.Label(summary_frame, text="Total Shortfall: 0.00 MWh")
        self.shortfall_label.pack(anchor="w")

        # Main content frame (for tables)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # --- Schedule Table ---
        schedule_frame = ttk.LabelFrame(content_frame, text="Dispatch Schedule (15-Minute Blocks)", padding="10")
        schedule_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        cols = ("Time Block", "Expected Demand", "Actual Demand", "Yesterday Rate", "Today Rate", "Scheduled Gen", "Shortfall/Surplus", "Block Cost")
        self.schedule_tree = ttk.Treeview(schedule_frame, columns=cols, show="headings")
        for col in cols:
            self.schedule_tree.heading(col, text=col)
            self.schedule_tree.column(col, width=130, anchor='center')
        
        # Add a scrollbar
        schedule_scrollbar = ttk.Scrollbar(schedule_frame, orient="vertical", command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=schedule_scrollbar.set)
        schedule_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.schedule_tree.pack(fill=tk.BOTH, expand=True)

        # --- Plant Details Table ---
        plant_frame = ttk.LabelFrame(content_frame, text="Plant Details", padding="10")
        plant_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        plant_cols = ("Name", "Type", "Capacity", "Rate", "Status", "Dispatch")
        self.plant_tree = ttk.Treeview(plant_frame, columns=plant_cols, show="headings")
        for col in plant_cols:
            self.plant_tree.heading(col, text=col)
            self.plant_tree.column(col, width=100, anchor='center')

        self.plant_tree.pack(fill=tk.BOTH, expand=True)
        self.plant_tree.tag_configure('ON', background='#dff0d8')
        self.plant_tree.tag_configure('OFF', background='#f2dede')
        self.plant_tree.tag_configure('FORCED_OUTAGE', background='#a94442', foreground='white')


    def _populate_initial_data(self):
        # Generate data for the schedule table
        self.demand_profile = self._generate_demand_profile()
        self.yesterday_rates = [random.uniform(1.5, 5.0) for _ in range(96)]

        for i in range(96):
            start_min = i * 15
            end_min = start_min + 15
            time_str = f"{start_min//60:02d}:{start_min%60:02d}-{end_min//60:02d}:{end_min%60:02d}"
            
            expected_demand = self.demand_profile[i]
            actual_demand = expected_demand * random.uniform(0.95, 1.05)
            
            self.schedule_tree.insert("", "end", iid=i, values=(
                time_str, 
                f"{expected_demand:.2f}", 
                f"{actual_demand:.2f}",
                f"₹{self.yesterday_rates[i]*1000:.2f}", # Assuming rate is in Rs/kWh, convert to MWh
                "N/A", "N/A", "N/A", "N/A"
            ))

        # Populate plant data
        self.update_plant_details()

    def update_plant_details(self):
        # Clear existing data
        for i in self.plant_tree.get_children():
            self.plant_tree.delete(i)
            
        # Insert new data
        for plant in self.scheduler.plants:
            tag = plant.status
            self.plant_tree.insert("", "end", values=(
                plant.name,
                plant.plant_type,
                f"{plant.capacity_mw:.2f} MW",
                f"₹{plant.rate_usd_per_mwh*100:.2f}", # Assuming rate is in paise/kWh, convert to Rs/MWh
                plant.status,
                f"{plant.current_dispatch_mw:.2f} MW"
            ), tags=(tag,))

    def run_next_block(self):
        if self.current_block >= 96:
            messagebox.showinfo("Simulation Complete", "24-hour simulation has finished.")
            self.run_button['state'] = 'disabled'
            return

        # Get data for the current block
        item = self.schedule_tree.item(self.current_block)
        values = item['values']
        actual_demand = float(values[2])
        
        # Run scheduler
        dispatched, shortfall, cost = self.scheduler.schedule_for_block(actual_demand, self.current_block)
        
        # Update schedule table
        self.schedule_tree.set(self.current_block, "Today Rate", f"₹{random.uniform(1.8, 6.0)*1000:.2f}")
        self.schedule_tree.set(self.current_block, "Scheduled Gen", f"{dispatched:.2f}")
        self.schedule_tree.set(self.current_block, "Shortfall/Surplus", f"{shortfall:.2f}")
        self.schedule_tree.set(self.current_block, "Block Cost", f"₹{cost:,.2f}")
        
        # Highlight current row and ensure it's visible
        self.schedule_tree.selection_set(self.current_block)
        self.schedule_tree.see(self.current_block)
        
        # Update summary and plant details
        self.update_summary()
        self.update_plant_details()
        
        self.current_block += 1

    def update_summary(self):
        summary = self.scheduler.daily_summary
        self.cost_label.config(text=f"Total Cost: ₹{summary['total_cost']:,.2f}")
        self.shortfall_label.config(text=f"Total Shortfall: {summary['total_shortfall_mwh']:.2f} MWh")

    def toggle_plant_status(self):
        selected_items = self.plant_tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a plant from the 'Plant Details' table first.")
            return
        
        selected_plant_name = self.plant_tree.item(selected_items[0])['values'][0]
        
        for plant in self.scheduler.plants:
            if plant.name == selected_plant_name:
                if plant.status == "ON":
                    plant.turn_off()
                elif plant.status == "OFF":
                    plant.turn_on()
                else:
                    messagebox.showinfo("Info", f"{plant.name} is in FORCED_OUTAGE and cannot be changed.")
                break
        self.update_plant_details()

    def declare_outage(self):
        selected_items = self.plant_tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a plant to declare an outage for.")
            return
            
        selected_plant_name = self.plant_tree.item(selected_items[0])['values'][0]
        
        for plant in self.scheduler.plants:
            if plant.name == selected_plant_name:
                plant.force_outage()
                break
        self.update_plant_details()

    def _generate_demand_profile(self, blocks=96, base=800, peak=1500):
        demand = []
        for i in range(blocks):
            radian = (i / blocks) * 2 * math.pi
            factor = (math.sin(radian - math.pi/2) + 1) / 2
            peak_factor = math.sin(radian * 2 - math.pi/2) * 0.15
            demand_value = base + (peak - base) * (factor + peak_factor)
            demand.append(max(base*0.9, demand_value))
        return demand

if __name__ == "__main__":
    # --- Initial Setup ---
    plant_portfolio = [
        PowerPlant(name="Coal Plant A", plant_type="COAL", capacity_mw=500, rate_usd_per_mwh=40, min_gen_mw=100),
        PowerPlant(name="Gas Plant B", plant_type="GAS", capacity_mw=300, rate_usd_per_mwh=65, min_gen_mw=50),
        PowerPlant(name="Solar Farm C", plant_type="SOLAR", capacity_mw=150, rate_usd_per_mwh=15, min_gen_mw=0),
        PowerPlant(name="Hydro Plant D", plant_type="HYDRO", capacity_mw=600, rate_usd_per_mwh=25, min_gen_mw=150),
        PowerPlant(name="Gas Peaker E", plant_type="GAS", capacity_mw=100, rate_usd_per_mwh=120, min_gen_mw=25),
    ]
    
    scheduler = Scheduler(plant_portfolio)
    app = PowerDashboard(scheduler)
    print("Initializing GUI... Window should appear now.")
    app.mainloop()
