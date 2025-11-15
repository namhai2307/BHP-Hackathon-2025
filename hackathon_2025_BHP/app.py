from flask import Flask, jsonify, request, render_template, send_file
from mooring_data_generator.builder import build_random_port
from mooring_data_generator.models import PortData
import json, random
from datetime import datetime
import os
import importlib
import mooring_data_generator.builder as builder_module

app = Flask(__name__)

# Store the port worker globally for updates
port_worker = None


def reset_generator_state():
    """Reset the mooring data generator to allow unlimited generations"""
    # Reload the builder module to reset the used names lists
    importlib.reload(builder_module)


def serialize_data(obj):
    """Helper function to serialize Pydantic models and other objects"""
    if hasattr(obj, '__dict__'):
        return str(obj)
    return obj


@app.route('/')
def home():
    """Home page with visual dashboard"""
    return render_template('index.html')


@app.route('/analysis')
def tension_analysis():
    """Tension analysis page"""
    return render_template('analysis.html')


@app.route('/api')
def api_docs():
    """API documentation endpoint"""
    return jsonify({
        "message": "Mooring Data Generator API",
        "endpoints": {
            "/api/port": "GET - Generate and retrieve random port data",
            "/api/port/berths": "GET - Get all berths in the current port",
            "/api/port/berth/<berth_name>": "GET - Get specific berth details",
            "/api/port/update": "POST - Update the port data (simulates real-time updates)",
            "/api/port/raw": "GET - Get raw port data as string"
        }
    })


@app.route('/api/port', methods=['GET'])
def get_port():
    """Generate and return random port data"""
    global port_worker
    
    try:
        # Reset generator state to prevent exhausting ship names
        reset_generator_state()
        
        # Re-import build_random_port after reload
        from mooring_data_generator.builder import build_random_port
        port_worker = build_random_port()
    except Exception as e:
        return jsonify({"error": f"Failed to generate port: {str(e)}"}), 500
    
    # Convert the port data to a serializable format
    port_data = port_worker.data
    
    return jsonify({
        "port_name": port_data.name,
        "total_berths": len(port_data.berths),
        "berths": [
            {
                "name": berth.name,
                "bollard_count": berth.bollard_count,
                "hook_count": berth.hook_count,
                "ship": {
                    "name": berth.ship.name,
                    "vessel_id": berth.ship.vessel_id
                } if berth.ship else None,
                "active_radars": len([r for r in berth.radars if r.distance_status == "ACTIVE"]),
                "total_radars": len(berth.radars)
            }
            for berth in port_data.berths
        ]
    })


@app.route('/api/port/berths', methods=['GET'])
def get_berths():
    """Get all berths with detailed information"""
    if not port_worker:
        return jsonify({"error": "No port data available. Call /api/port first"}), 404
    
    port_data = port_worker.data
    berths_data = []
    
    for berth in port_data.berths:
        berth_info = {
            "name": berth.name,
            "bollard_count": berth.bollard_count,
            "hook_count": berth.hook_count,
            "ship": {
                "name": berth.ship.name,
                "vessel_id": berth.ship.vessel_id
            } if berth.ship else None,
            "radars": [
                {
                    "name": radar.name,
                    "ship_distance": radar.ship_distance,
                    "distance_change": radar.distance_change,
                    "status": radar.distance_status
                }
                for radar in berth.radars
            ],
            "bollards": [
                {
                    "name": bollard.name,
                    "hooks": [
                        {
                            "name": hook.name,
                            "tension": hook.tension if hook.tension is not None else None,
                            "faulted": hook.faulted,
                            "attached_line": hook.attached_line
                        }
                        for hook in bollard.hooks
                    ]
                }
                for bollard in berth.bollards
            ]
        }
        berths_data.append(berth_info)
    
    return jsonify({
        "port_name": port_data.name,
        "berths": berths_data
    })


@app.route('/api/port/berth/<berth_name>', methods=['GET'])
def get_berth(berth_name):
    """Get specific berth details by name"""
    if not port_worker:
        return jsonify({"error": "No port data available. Call /api/port first"}), 404
    
    port_data = port_worker.data
    
    # Find the berth
    berth = next((b for b in port_data.berths if b.name == berth_name), None)
    
    if not berth:
        return jsonify({"error": f"Berth '{berth_name}' not found"}), 404
    
    return jsonify({
        "name": berth.name,
        "bollard_count": berth.bollard_count,
        "hook_count": berth.hook_count,
        "ship": {
            "name": berth.ship.name,
            "vessel_id": berth.ship.vessel_id
        } if berth.ship else None,
        "radars": [
            {
                "name": radar.name,
                "ship_distance": radar.ship_distance,
                "distance_change": radar.distance_change,
                "status": radar.distance_status
            }
            for radar in berth.radars
        ],
        "bollards": [
            {
                "name": bollard.name,
                "hooks": [
                    {
                        "name": hook.name,
                        "tension": hook.tension if hook.tension is not None else None,
                        "faulted": hook.faulted,
                        "attached_line": hook.attached_line
                    }
                    for hook in bollard.hooks
                ]
            }
            for bollard in berth.bollards
        ]
    })


@app.route('/api/port/update', methods=['POST'])
def update_port():
    """Update port data - simulates real-time data changes"""
    global port_worker
    
    if not port_worker:
        return jsonify({"error": "No port data available. Call /api/port first"}), 404
    
    # Update the port worker (this simulates new readings)
    port_worker.update()
    
    return jsonify({
        "message": "Port data updated successfully",
        "port_name": port_worker.data.name
    })


@app.route('/api/port/raw', methods=['GET'])
def get_raw_port():
    """Get raw port data as string representation"""
    if not port_worker:
        return jsonify({"error": "No port data available. Call /api/port first"}), 404
    
    return jsonify({
        "raw_data": str(port_worker.data)
    })


@app.route('/api/port/statistics', methods=['GET'])
def get_statistics():
    """Get statistics about the current port"""
    if not port_worker:
        return jsonify({"error": "No port data available. Call /api/port first"}), 404
    
    port_data = port_worker.data
    
    total_bollards = sum(berth.bollard_count for berth in port_data.berths)
    total_hooks = sum(berth.hook_count for berth in port_data.berths)
    
    active_hooks = 0
    faulted_hooks = 0
    total_tension = 0
    
    for berth in port_data.berths:
        for bollard in berth.bollards:
            for hook in bollard.hooks:
                if hook.attached_line:
                    active_hooks += 1
                if hook.faulted:
                    faulted_hooks += 1
                if hook.tension is not None:
                    total_tension += hook.tension
    
    return jsonify({
        "port_name": port_data.name,
        "total_berths": len(port_data.berths),
        "total_bollards": total_bollards,
        "total_hooks": total_hooks,
        "active_hooks": active_hooks,
        "faulted_hooks": faulted_hooks,
        "total_tension": total_tension,
        "ships_docked": sum(1 for berth in port_data.berths if berth.ship)
    })


@app.route('/api/port/analysis', methods=['GET'])
def get_tension_analysis():
    """Get prioritized bollard analysis data"""
    if not port_worker:
        return jsonify({"error": "No port data available. Generate port data first"}), 404
    
    port_data = port_worker.data
    all_bollards = []
    
    # Collect all bollards from all berths with priority metrics
    for berth in port_data.berths:
        for bollard in berth.bollards:
            # Collect hook data
            hooks_data = [(hook, hook.tension if hook.tension is not None else None) for hook in bollard.hooks]
            
            critical_count = sum(1 for hook, tension in hooks_data if not hook.faulted and tension is not None and tension >= 86)
            dangerous_count = sum(1 for hook, tension in hooks_data if not hook.faulted and tension is not None and 70 <= tension <= 85)
            attention_count = sum(1 for hook, tension in hooks_data if not hook.faulted and tension is not None and 40 <= tension <= 69)
            faulted_count = sum(1 for hook, tension in hooks_data if hook.faulted)
            total_tension = sum(tension for hook, tension in hooks_data if tension is not None)
            
            bollard_info = {
                "berth_name": berth.name,
                "bollard_name": bollard.name,
                "ship_name": berth.ship.name if berth.ship else "No Ship",
                "vessel_id": berth.ship.vessel_id if berth.ship else "N/A",
                "critical_count": critical_count,
                "dangerous_count": dangerous_count,
                "attention_count": attention_count,
                "faulted_count": faulted_count,
                "total_tension": total_tension,
                "hooks": [
                    {
                        "name": hook.name,
                        "tension": tension,
                        "faulted": hook.faulted,
                        "attached_line": hook.attached_line
                    }
                    for hook, tension in hooks_data
                ]
            }
            all_bollards.append(bollard_info)
    
    # Sort by: 1. Critical hooks (desc), 2. Faulted hooks (desc), 3. Total tension (desc)
    all_bollards.sort(key=lambda x: (x["critical_count"], x["faulted_count"], x["total_tension"]), reverse=True)
    
    return jsonify({
        "port_name": port_data.name,
        "total_bollards": len(all_bollards),
        "bollards": all_bollards
    })


@app.route('/api/port/download', methods=['GET'])
def download_port_data():
    """Download current port data as JSON file"""
    if not port_worker:
        return jsonify({"error": "No port data available. Generate port data first"}), 404
    
    port_data = port_worker.data
    
    # Create a comprehensive JSON structure
    data_export = {
        "timestamp": datetime.now().isoformat(),
        "port_name": port_data.name,
        "total_berths": len(port_data.berths),
        "berths": []
    }
    
    for berth in port_data.berths:
        berth_data = {
            "name": berth.name,
            "bollard_count": berth.bollard_count,
            "hook_count": berth.hook_count,
            "ship": {
                "name": berth.ship.name,
                "vessel_id": berth.ship.vessel_id
            } if berth.ship else None,
            "radars": [
                {
                    "name": radar.name,
                    "ship_distance": radar.ship_distance,
                    "distance_change": radar.distance_change,
                    "status": radar.distance_status
                }
                for radar in berth.radars
            ],
            "bollards": [
                {
                    "name": bollard.name,
                    "hooks": [
                        {
                            "name": hook.name,
                            "tension": hook.tension if hook.tension is not None else None,
                            "faulted": hook.faulted,
                            "attached_line": hook.attached_line
                        }
                        for hook in bollard.hooks
                    ]
                }
                for bollard in berth.bollards
            ]
        }
        data_export["berths"].append(berth_data)
    
    return jsonify(data_export)


if __name__ == '__main__':
    print("Starting Mooring Data Generator Flask API...")
    print("Visit http://localhost:5000 for the visual dashboard")
    print("Visit http://localhost:5000/api for API documentation")
    app.run(debug=True, host='0.0.0.0', port=5000)
