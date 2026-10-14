import fabric_control as fc

OUTPUTS = []

if __name__ == "__main__":
    fc.sync_policies()
    fc.verify_policies()
    print("policies synced and verified", flush=True)
