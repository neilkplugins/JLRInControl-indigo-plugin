# JLRInControlIndigo
An I-Pace Plugin for Indigo Domotics (That will also support ICE Jaguar and Land Rover Vehicles JLR

This plugin uses the excellent work here https://github.com/ardevd/jlrpy to access Jaguar / Land Rover (JLR) cars that have the InControl Pro system.  The primary capabilities are :-

1) Expose a huge amount of vehicle data in the form of Device States (Including location, fluid levels, tyre pressures, range, charge states, time needed to charge,  journey details and more)
2) Uses the MapQuest API to produce a car location image that can be used on control pages (requires a free API key)
3) Can initiate or stop charging (to take advantage of lower energy rates) or limit charge to a specified State of Charge (SoC) using the associated triggers
4) Can initiate pre-conditioning including cabin temperature to both extend range and for comfort
