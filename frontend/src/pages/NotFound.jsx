import React from "react";
import { ArrowLeft, Compass } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotFound(){return <div className="not-found"><Compass size={44}/><span className="eyebrow">404</span><h1>Page not found</h1><p>The page you requested does not exist.</p><Link className="primary-btn" to="/"><ArrowLeft size={16}/> Back to overview</Link></div>;}
