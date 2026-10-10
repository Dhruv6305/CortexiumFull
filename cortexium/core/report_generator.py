import os
import time
import tempfile
import traceback
import json
from config import DATA_DIR

class ReportGenerator:
    @staticmethod
    def generate_pdf(logs, output_path=None, history=None):
        """
        Generates a professional PDF session analytics report from logs,
        incorporating multi-session trends and performance improvements.
        """
        try:
            # Prevent matplotlib from trying to open a GUI window
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from fpdf import FPDF
        except ImportError as e:
            print(f"⚠️ Warning: Could not generate session safety report because of missing dependencies ({e}). Please run: pip install matplotlib fpdf2")
            return None

        if not logs:
            print("⚠️ Cannot generate report: Session logs are empty.")
            return None
            
        if output_path is None:
            timestamp = int(time.time())
            output_path = f"session_report_{timestamp}.pdf"
            
        # 1. Compute summary statistics
        duration = logs[-1]['timestamp']
        scores = [log['score'] for log in logs]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        final_score = scores[-1] if scores else 0.0
        
        tailgating_count = sum(1 for log in logs if log['tailgating'])
        lane_drift_count = sum(1 for log in logs if log['lane_drift'])
        unstable_steering_count = sum(1 for log in logs if log['unstable_steering'])
        collision_risk_count = sum(1 for log in logs if log['collision_risk'])
        
        # 2. Find key moments (3 lowest dips, separated by at least 5 seconds)
        sorted_logs = sorted(logs, key=lambda x: x['score'])
        dips = []
        for log in sorted_logs:
            far_enough = True
            for dip in dips:
                if abs(log['timestamp'] - dip['timestamp']) < 5.0:
                    far_enough = False
                    break
            if far_enough:
                dips.append(log)
                if len(dips) == 3:
                    break
                    
        # Sort dips back into chronological order
        dips = sorted(dips, key=lambda x: x['timestamp'])
        
        def get_dominant_cause(log):
            if log['collision_risk']:
                return "Collision Risk"
            elif log['tailgating']:
                return "Tailgating"
            elif log['lane_drift']:
                return "Lane Drift"
            elif log['unstable_steering']:
                return "Unstable Steering"
            return "General Inattention"

        # 3. Generate charts using Matplotlib
        temp_dir = tempfile.gettempdir()
        score_chart_path = os.path.join(temp_dir, "temp_score_chart.png")
        violation_chart_path = os.path.join(temp_dir, "temp_violation_chart.png")
        trend_chart_path = os.path.join(temp_dir, "temp_trend_chart.png")
        
        has_trend_chart = False
        
        # Load history if not passed in
        if history is None:
            history_file = os.path.join(DATA_DIR, 'session_history.json')
            try:
                if os.path.exists(history_file):
                    with open(history_file, 'r') as f:
                        history = json.load(f)
            except Exception:
                pass
        
        try:
            # Chart A: Score over time
            plt.figure(figsize=(6, 3))
            timestamps = [log['timestamp'] for log in logs]
            plt.plot(timestamps, scores, color='#00a8cc', linewidth=2, label='Safety Score')
            plt.axhline(y=50, color='#ff5722', linestyle='--', alpha=0.7, label='Critical Limit')
            plt.title('Safety Score Trajectory', fontsize=12, fontweight='bold', pad=10)
            plt.xlabel('Elapsed Time (seconds)', fontsize=9)
            plt.ylabel('Safety Score', fontsize=9)
            plt.ylim(0, 105)
            plt.grid(True, linestyle=':', alpha=0.6)
            plt.legend(loc='lower left', fontsize=8)
            plt.tight_layout()
            plt.savefig(score_chart_path, dpi=300)
            plt.close()
            
            # Chart B: Violations Bar Chart
            plt.figure(figsize=(6, 3))
            labels = ['Collision Risk', 'Tailgating', 'Lane Drift', 'Unstable Steering']
            counts = [collision_risk_count, tailgating_count, lane_drift_count, unstable_steering_count]
            colors = ['#ff5722', '#ffb142', '#33d9b2', '#706fd3']
            
            plt.bar(labels, counts, color=colors, edgecolor='none', width=0.5)
            plt.title('Safety Violations Summary', fontsize=12, fontweight='bold', pad=10)
            plt.xlabel('Violation Type', fontsize=9)
            plt.ylabel('Incident Count (Frames)', fontsize=9)
            plt.xticks(fontsize=8)
            plt.grid(axis='y', linestyle=':', alpha=0.6)
            plt.tight_layout()
            plt.savefig(violation_chart_path, dpi=300)
            plt.close()
            
            # Chart C: Score Trend across sessions
            if history and len(history) >= 2:
                plt.figure(figsize=(6, 3))
                session_indices = list(range(1, len(history) + 1))
                avg_scores = [session['avg_score'] for session in history]
                
                plt.plot(session_indices, avg_scores, color='#2ecc71', marker='o', linewidth=2, label='Avg Safety Score')
                plt.title('Multi-Session Safety Trend', fontsize=12, fontweight='bold', pad=10)
                plt.xlabel('Session Index', fontsize=9)
                plt.ylabel('Average Score', fontsize=9)
                plt.ylim(50, 105)
                plt.xticks(session_indices)
                plt.grid(True, linestyle=':', alpha=0.6)
                plt.legend(loc='lower left', fontsize=8)
                plt.tight_layout()
                plt.savefig(trend_chart_path, dpi=300)
                plt.close()
                has_trend_chart = True
                
        except Exception as e:
            print(f"⚠️ Error creating Matplotlib charts: {e}")
            traceback.print_exc()
            
        # 4. Generate PDF Report using FPDF2
        try:
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.set_margins(15, 15, 15)
            pdf.add_page()
            
            # Header Styling
            pdf.set_fill_color(30, 30, 30) # Dark top bar
            pdf.rect(0, 0, 210, 35, 'F')
            
            pdf.set_y(8)
            pdf.set_font('helvetica', 'B', 18)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 10, 'CORTEXIUM XR - DRIVING SAFETY REPORT', ln=True, align='C')
            
            pdf.set_y(38) # Just below the dark header block
            pdf.set_text_color(30, 30, 30)
            
            # Metadata Section
            pdf.set_font('helvetica', 'B', 12)
            pdf.cell(0, 8, 'Session Statistics', ln=True)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(3)
            
            pdf.set_font('helvetica', '', 10)
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(logs[0]['timestamp'] + time.time() - duration))
            pdf.cell(90, 6, f'Date & Time:  {date_str}', ln=False)
            pdf.cell(90, 6, f'Average Score:  {avg_score:.1f} / 100', ln=True)
            pdf.cell(90, 6, f'Duration:       {duration:.1f} seconds', ln=False)
            pdf.cell(90, 6, f'Final Score:    {final_score:.1f} / 100', ln=True)
            pdf.ln(5)
            
            # Graphs Section (Side-by-side or stacked)
            pdf.set_font('helvetica', 'B', 12)
            pdf.cell(0, 8, 'Session Visual Analytics', ln=True)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(4)
            
            # Embed score chart
            if os.path.exists(score_chart_path):
                # 85mm width, 45mm height
                pdf.image(score_chart_path, x=15, y=pdf.get_y(), w=85, h=45)
                
            # Embed violations chart
            if os.path.exists(violation_chart_path):
                pdf.image(violation_chart_path, x=110, y=pdf.get_y(), w=85, h=45)
                
            pdf.set_y(pdf.get_y() + 48) # Skip past the charts
            
            # Key Moments Section
            pdf.set_font('helvetica', 'B', 12)
            pdf.cell(0, 8, 'Key Safety Dips (Lowest 3 Moments)', ln=True)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(4)
            
            # Table Header
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(40, 8, 'Timestamp (sec)', border=1, align='C', fill=True)
            pdf.cell(40, 8, 'Safety Score', border=1, align='C', fill=True)
            pdf.cell(50, 8, 'Dominant Cause', border=1, align='C', fill=True)
            pdf.cell(50, 8, 'Distance to Lead Car', border=1, align='C', fill=True, ln=True)
            
            # Table Data
            pdf.set_font('helvetica', '', 10)
            if not dips:
                pdf.cell(180, 8, 'No significant safety score drops detected.', border=1, align='C', ln=True)
            else:
                for dip in dips:
                    ts = f"{dip['timestamp']:.1f}s"
                    score_val = str(int(dip['score']))
                    cause = get_dominant_cause(dip)
                    dist = f"{dip['distance']:.1f}m" if dip['distance'] is not None else "N/A"
                    
                    pdf.cell(40, 8, ts, border=1, align='C')
                    pdf.cell(40, 8, score_val, border=1, align='C')
                    pdf.cell(50, 8, cause, border=1, align='C')
                    pdf.cell(50, 8, dist, border=1, align='C', ln=True)
            pdf.ln(5)
            
            # Summary / Conclusion
            pdf.set_font('helvetica', 'B', 12)
            pdf.cell(0, 8, 'Safety Evaluation Overview', ln=True)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(4)
            
            pdf.set_font('helvetica', '', 10)
            if avg_score >= 80:
                conclusion = "Excellent driver awareness. Safety telemetry shows optimal lane stability and safe vehicle-following behaviors."
            elif avg_score >= 60:
                conclusion = "Moderate safety warning. Minor steering drift or close tailgating instances were detected during this driving session. Caution advised."
            else:
                conclusion = "CRITICAL SAFETY RISK: Major safety scoring dips logged. Frequent lane deviation or close-proximity vehicle following detected. Immediate safety feedback intervention recommended."
                
            pdf.multi_cell(0, 6, conclusion)
            
            # If multi-session history is available, draw a Second Page for trends!
            if history and len(history) >= 2:
                pdf.add_page()
                
                # Header Styling (Page 2)
                pdf.set_fill_color(30, 30, 30) # Dark top bar
                pdf.rect(0, 0, 210, 35, 'F')
                
                pdf.set_y(8)
                pdf.set_font('helvetica', 'B', 18)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(0, 10, 'CORTEXIUM XR - MULTI-SESSION ANALYTICS', ln=True, align='C')
                
                pdf.set_y(38)
                pdf.set_text_color(30, 30, 30)
                
                # Trend Chart Section
                pdf.set_font('helvetica', 'B', 12)
                pdf.cell(0, 8, 'Safety Score Improvement Trend', ln=True)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(4)
                
                if has_trend_chart and os.path.exists(trend_chart_path):
                    # Center the chart (width=120, height=60)
                    pdf.image(trend_chart_path, x=45, y=pdf.get_y(), w=120, h=60)
                    pdf.set_y(pdf.get_y() + 64)
                    
                # Historical Comparison Table Section
                pdf.set_font('helvetica', 'B', 12)
                pdf.cell(0, 8, 'Driving Session Comparisons', ln=True)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(4)
                
                # Table Header
                pdf.set_font('helvetica', 'B', 9)
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(35, 8, 'Session Index', border=1, align='C', fill=True)
                pdf.cell(40, 8, 'Duration (min)', border=1, align='C', fill=True)
                pdf.cell(45, 8, 'Avg Score', border=1, align='C', fill=True)
                pdf.cell(60, 8, 'Total Violations', border=1, align='C', fill=True, ln=True)
                
                # Table Data
                pdf.set_font('helvetica', '', 9)
                for idx, session in enumerate(history):
                    total_violations = session['tailgating'] + session['lane_drift'] + session['unstable_steering'] + session['collision_risk']
                    duration_min = f"{session['duration'] / 60.0:.1f}m"
                    is_current_indicator = " (Current)" if idx == len(history) - 1 else ""
                    
                    pdf.cell(35, 8, f"Run {idx + 1}{is_current_indicator}", border=1, align='C')
                    pdf.cell(40, 8, duration_min, border=1, align='C')
                    pdf.cell(45, 8, f"{session['avg_score']:.1f}", border=1, align='C')
                    pdf.cell(60, 8, str(total_violations), border=1, align='C', ln=True)
                    
                pdf.ln(5)
                
                # Trend Analyzer Feedback Section
                pdf.set_font('helvetica', 'B', 12)
                pdf.cell(0, 8, 'Trend Coaching Insights', ln=True)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(4)
                
                pdf.set_font('helvetica', '', 10)
                from core.trend_analyzer import TrendAnalyzer
                trends = TrendAnalyzer.analyze_trends(history)
                
                # Sanitize text for PDF formatting (replace/strip unicode emojis to prevent helvetica encoding exceptions)
                feedback_text = trends['feedback']
                replacements = {
                    "⚠": "[Warning]",
                    "✅": "[Achievement]",
                    "📈": "",
                    "🎉": "",
                    "💡": "",
                    "🎯": ""
                }
                for emo, clean in replacements.items():
                    feedback_text = feedback_text.replace(emo, clean)
                feedback_text = feedback_text.encode('ascii', errors='ignore').decode('ascii')
                
                pdf.multi_cell(0, 6, feedback_text)
            
            # Save the PDF file
            pdf.output(output_path)
            print(f"📄 Session safety report successfully generated and saved to: {output_path}")
            
        except Exception as e:
            print(f"⚠️ Error creating PDF report document: {e}")
            traceback.print_exc()
            
        # 5. Clean up temporary chart images
        try:
            if os.path.exists(score_chart_path):
                os.remove(score_chart_path)
            if os.path.exists(violation_chart_path):
                os.remove(violation_chart_path)
            if has_trend_chart and os.path.exists(trend_chart_path):
                os.remove(trend_chart_path)
        except Exception:
            pass
            
        return output_path
